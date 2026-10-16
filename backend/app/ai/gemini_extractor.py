"""Gemini Vision AI Aircraft Blueprint Extractor.

Leverages Gemini 2.5 / 1.5 Multimodal API to semantically analyze orthographic
drawings (Top, Side, Front) and extract precise parametric specifications
(AircraftSemanticSpec) without manual template bias.
"""

from __future__ import annotations

import io
import json
import logging
import math
import os
from pathlib import Path
from typing import BinaryIO

import numpy as np
from PIL import Image

from app.ai.spec import (
    AircraftSemanticSpec,
    CockpitSpec,
    FuselageSpec,
    FuselageStationSpec,
    HorizontalStabSpec,
    PropulsionSpec,
    TailSpec,
    VerticalFinSpec,
    WingSpec,
)

logger = logging.getLogger(__name__)


class GeminiBlueprintExtractor:
    """Multimodal aerospace blueprint analyzer using Gemini Vision."""

    def __init__(self, api_key: str | None = None, model_name: str = "gemini-3.8-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name

    def analyze_views(
        self,
        top_image: bytes | Path | Image.Image | None = None,
        side_image: bytes | Path | Image.Image | None = None,
        front_image: bytes | Path | Image.Image | None = None,
        unified_blueprint: bytes | Path | Image.Image | None = None,
        wingspan_hint_m: float | None = None,
        length_hint_m: float | None = None,
        height_hint_m: float | None = None,
        aircraft_name_hint: str | None = None,
    ) -> AircraftSemanticSpec:
        """
        Analyze orthographic views using Gemini Vision and return an AircraftSemanticSpec.
        Falls back to clean parametric extraction if Gemini API key is unavailable.
        """
        if self.api_key:
            try:
                return self._call_gemini_vision(
                    top_image=top_image,
                    side_image=side_image,
                    front_image=front_image,
                    unified_blueprint=unified_blueprint,
                    wingspan_m=wingspan_hint_m or 11.0,
                    length_m=length_hint_m or 11.0,
                    height_m=height_hint_m or 3.5,
                    aircraft_name=aircraft_name_hint or "Detected Aircraft",
                )
            except Exception as e:
                logger.warning("Gemini Vision API call failed: %s. Using heuristic extractor.", e)

        # Fallback heuristic extractor (guarantees smooth non-polluted model even offline)
        return self._generate_heuristic_spec(
            wingspan_m=wingspan_hint_m or 11.0,
            length_m=length_hint_m or 11.0,
            height_m=height_hint_m or 3.5,
            aircraft_name=aircraft_name_hint or "Aircraft",
        )

    def _call_gemini_vision(
        self,
        top_image: bytes | Path | Image.Image | None,
        side_image: bytes | Path | Image.Image | None,
        front_image: bytes | Path | Image.Image | None,
        unified_blueprint: bytes | Path | Image.Image | None,
        wingspan_m: float,
        length_m: float,
        height_m: float,
        aircraft_name: str,
    ) -> AircraftSemanticSpec:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)

        contents = []

        def to_pil(img_input):
            if isinstance(img_input, Image.Image):
                return img_input
            if isinstance(img_input, (str, Path)):
                return Image.open(str(img_input)).convert("RGB")
            if isinstance(img_input, bytes):
                return Image.open(io.BytesIO(img_input)).convert("RGB")
            return None

        pil_top = to_pil(top_image)
        pil_side = to_pil(side_image)
        pil_front = to_pil(front_image)
        pil_unified = to_pil(unified_blueprint)

        if pil_top:
            contents.extend(["[VIEW: TOP / PLAN VIEW (Looking down from above - X is span, Z is length)]", pil_top])
        if pil_side:
            contents.extend(["[VIEW: SIDE / ELEVATION VIEW (Looking from side - Z is length, Y is height)]", pil_side])
        if pil_front:
            contents.extend(["[VIEW: FRONT / CROSS-SECTION VIEW (Looking from front - X is span, Y is height)]", pil_front])
        if pil_unified and not (pil_top or pil_side):
            contents.extend(["[3-VIEW ORTHOGRAPHIC BLUEPRINT (Contains Top, Side, and Front views)]", pil_unified])

        prompt = f"""
You are an expert aeronautical CAD reverse-engineering system.
Analyze the provided orthographic drawing of the aircraft '{aircraft_name}'.
Approximate overall dimensions: Wingspan={wingspan_m:.2f}m, Length={length_m:.2f}m, Height={height_m:.2f}m.

CRITICAL AERONAUTICAL EXTRACTION RULES:
1. AIRCRAFT CLASSIFICATION & PROPULSION:
   - Identify aircraft_type: 'airliner' (for commercial passenger jets like Boeing 737, 777, A320), 'fighter_jet', 'trainer', 'cargo', 'glider'.
   - Determine engine type (propulsion.type):
     * 'jet_pod_underwing' if turbofan pods hang under the wings (like Boeing 737, A320).
       Provide: nacelle_radius (usually 0.8m-1.1m), nacelle_length (3.5m-4.5m), nacelle_offset_x (~28% of wingspan), nacelle_z.
     * 'jet_internal' if internal jet engine with rear fuselage exhaust nozzles.
     * 'propeller_nose' if a single tractor propeller is on the nose (give num_blades).

2. FUSELAGE:
   - Provide 14 to 16 stations along the fuselage from nose (+Z) to tail (-Z).
   - In each station, measure the AERODYNAMIC BODY CONTOUR ONLY (DO NOT include wings or landing gear!).
   - For AIRLINERS:
     * The nose radome is ROUNDED and parabolic (NOT a sharp needle point!).
     * The middle ~55% of the fuselage (passenger cabin) has a CONSTANT CYLINDRICAL CROSS-SECTION (constant half_width_m and height).
     * The tail cone sweeps upward at the belly to the APU.
     * Set cockpit.present = false (airliners have integrated cockpit windows, NOT bubble canopies).
   - For FIGHTERS/TRAINERS:
     * Set cockpit.present = true with bubble canopy dimensions.

3. WINGS & WINGLETS:
   - Observe actual planform in Top view: extract real leading edge sweep angle (e.g. 25° for 737, 35° for fighters).
   - Extract dihedral_deg from Front view (usually 4° to 6°).
   - If wingtip winglets or split-scimitar winglets are present, set has_winglets = true and winglet_height_m.

4. TAIL / EMPENNAGE:
   - If vertical fin has a forward dorsal fillet extension along the fuselage spine, set has_dorsal_fin = true.
   - Extract vertical fin sweep (e.g. 35° for airliners) and horizontal stabilizer sweep.

Output the result strictly adhering to the JSON schema.
"""
        contents.append(prompt)

        response = client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AircraftSemanticSpec,
                temperature=0.1,
            ),
        )

        raw_json = response.text
        spec_dict = json.loads(raw_json)
        return AircraftSemanticSpec.model_validate(spec_dict)

    def _generate_heuristic_spec(
        self,
        wingspan_m: float,
        length_m: float,
        height_m: float,
        aircraft_name: str,
    ) -> AircraftSemanticSpec:
        """
        Generate a clean, mathematically smooth aerodynamic specification.
        Adapts geometry to aircraft class: commercial airliners, fighter jets, or trainers.
        """
        name_lower = (aircraft_name or "").lower()
        is_airliner = (
            any(k in name_lower for k in [
                "737", "320", "airbus", "boeing", "max", "embraer", "bombardier",
                "airliner", "commercial", "passenger", "jetliner", "transport",
                "777", "787", "747", "330", "350", "e190", "e195", "a321", "a319",
            ])
            or length_m >= 22.0
            or wingspan_m >= 22.0
        )
        is_fighter = any(k in name_lower for k in [
            "f-", "fa-", "su-", "mig", "mirage", "gripen", "fighter", "rafele",
            "typhoon", "eagle", "falcon", "stealth", "interceptor", "f15", "f16", "f18", "f22", "f35",
        ])

        nose_z = length_m * 0.46
        tail_z = nose_z - length_m
        num_stations = 16

        z_coords = np.linspace(nose_z, tail_z, num_stations)
        stations: list[FuselageStationSpec] = []

        if is_airliner:
            # Commercial Airliner (e.g. Boeing 737 MAX, Airbus A320)
            max_w = max(2.8, min(6.2, length_m * 0.098))  # ~3.8m diameter for 737
            max_h = max_w * 1.05

            for i, z in enumerate(z_coords):
                u = float(i / (num_stations - 1))
                if u < 0.18:
                    # Aerodynamic rounded radome (elliptic expansion from blunt tip)
                    radome_tip = 0.38
                    env = radome_tip + (1.0 - radome_tip) * math.sqrt(max(0.0, u / 0.18))
                    half_w = (max_w / 2.0) * env
                    half_h = (max_h / 2.0) * env
                    y_top = (max_h / 2.0) * (0.45 + 0.55 * math.sqrt(max(0.0, u / 0.18)))
                    y_bot = -half_h * (0.60 + 0.40 * (u / 0.18))
                elif u <= 0.72:
                    # Constant Passenger Cabin Tube
                    half_w = max_w / 2.0
                    half_h = max_h / 2.0
                    y_top = max_h / 2.0
                    y_bot = -max_h / 2.0
                else:
                    # Tail cone tapering to APU exhaust with upward belly upsweep
                    tu = (u - 0.72) / 0.28
                    t_env = max(0.12, 1.0 - 0.82 * (tu ** 1.35))
                    half_w = (max_w / 2.0) * t_env
                    y_top = (max_h / 2.0) * (1.0 - 0.45 * tu)
                    y_bot = -(max_h / 2.0) + (max_h * 0.76) * (tu ** 1.4)

                stations.append(
                    FuselageStationSpec(
                        u=round(u, 3),
                        z_m=round(float(z), 3),
                        y_top_m=round(y_top, 3),
                        y_bot_m=round(y_bot, 3),
                        half_width_m=round(half_w, 3),
                    )
                )

            cockpit = CockpitSpec(present=False)
            fuselage = FuselageSpec(stations=stations, cockpit=cockpit)

            semi_span = wingspan_m / 2.0
            root_chord = length_m * 0.19
            tip_chord = root_chord * 0.25

            wings = WingSpec(
                planform="swept",
                span_m=round(semi_span - max_w * 0.48, 3),
                root_chord_m=round(root_chord, 3),
                tip_chord_m=round(tip_chord, 3),
                sweep_leading_edge_deg=25.0,  # Boeing 737 25° sweep
                dihedral_deg=5.5,
                root_x=round(max_w * 0.48, 3),
                root_y=round(-max_h * 0.35, 3),
                root_z=round(nose_z - length_m * 0.44, 3),
                thickness_ratio=0.12,
                has_winglets=True,
                winglet_height_m=1.45,
            )

            v_fin = VerticalFinSpec(
                name="rudder_1",
                height_m=round(height_m * 0.58, 3),
                root_chord_m=round(length_m * 0.18, 3),
                tip_chord_m=round(length_m * 0.07, 3),
                sweep_deg=35.0,
                offset_x=0.0,
                root_y=round(max_h * 0.32, 3),
                root_z=round(tail_z + length_m * 0.18, 3),
            )

            h_stab = HorizontalStabSpec(
                present=True,
                semi_span_m=round(wingspan_m * 0.19, 3),
                root_chord_m=round(length_m * 0.12, 3),
                tip_chord_m=round(length_m * 0.05, 3),
                sweep_deg=28.0,
                root_y=round(max_h * 0.18, 3),
                root_z=round(tail_z + length_m * 0.10, 3),
            )

            tail = TailSpec(
                configuration="conventional",
                horizontal_stabilizer=h_stab,
                vertical_fins=[v_fin],
                has_dorsal_fin=True,
                dorsal_fin_length_m=round(length_m * 0.08, 3),
            )

            propulsion = PropulsionSpec(
                type="jet_pod_underwing",
                nacelle_count=2,
                nacelle_radius=0.92,  # CFM LEAP-1B 1.84m cowl diameter
                nacelle_length=3.80,
                nacelle_offset_x=round(wingspan_m * 0.28, 3),  # Underwing position
                nacelle_z=round(wings.root_z + 1.20, 3),  # Forward slung underwing
                thrustline_y=round(-max_h * 0.42, 3),
            )

            return AircraftSemanticSpec(
                aircraft_name=aircraft_name,
                aircraft_type="airliner",
                wingspan_m=round(wingspan_m, 2),
                length_m=round(length_m, 2),
                height_m=round(height_m, 2),
                fuselage=fuselage,
                wings=wings,
                tail=tail,
                propulsion=propulsion,
            )

        # Standard Fighter / Trainer Aerodynamic Hull
        max_w = min(1.8, length_m * 0.12) if not is_fighter else max(1.6, length_m * 0.13)
        max_h = min(2.0, height_m * 0.45)

        for i, z in enumerate(z_coords):
            u = float(i / (num_stations - 1))
            if u < 0.25:
                radome_tip = 0.25
                env = radome_tip + (1.0 - radome_tip) * math.sin((u / 0.25) * (math.pi / 2))
            else:
                env = math.cos(((u - 0.25) / 0.75) * (math.pi / 2.15))
            env = max(0.08, float(env))

            half_w = float((max_w / 2.0) * env)
            half_h = float((max_h / 2.0) * env)

            y_top = float(half_h)
            y_bot = float(-half_h * 0.85)

            stations.append(
                FuselageStationSpec(
                    u=round(u, 3),
                    z_m=round(float(z), 3),
                    y_top_m=round(y_top, 3),
                    y_bot_m=round(y_bot, 3),
                    half_width_m=round(half_w, 3),
                )
            )

        cockpit = CockpitSpec(
            present=True,
            start_z=round(nose_z - length_m * 0.16, 3),
            end_z=round(nose_z - length_m * 0.50, 3),
            max_height=round(height_m * 0.16, 3),
            max_half_width=round(max_w * 0.42, 3),
        )

        fuselage = FuselageSpec(stations=stations, cockpit=cockpit)

        semi_span = wingspan_m / 2.0
        root_chord = length_m * (0.28 if is_fighter else 0.20)
        tip_chord = root_chord * (0.35 if is_fighter else 0.48)

        wings = WingSpec(
            planform="swept" if is_fighter else "tapered",
            span_m=round(semi_span - max_w * 0.5, 3),
            root_chord_m=round(root_chord, 3),
            tip_chord_m=round(tip_chord, 3),
            sweep_leading_edge_deg=32.0 if is_fighter else 5.0,
            dihedral_deg=2.0 if is_fighter else 4.5,
            root_x=round(max_w * 0.5, 3),
            root_y=-0.10,
            root_z=round(nose_z - length_m * 0.40, 3),
            thickness_ratio=0.10 if is_fighter else 0.13,
            has_winglets=False,
        )

        v_fin = VerticalFinSpec(
            name="rudder_1",
            height_m=round(height_m * 0.52, 3),
            root_chord_m=round(length_m * 0.18, 3),
            tip_chord_m=round(length_m * 0.08, 3),
            sweep_deg=28.0 if is_fighter else 20.0,
            offset_x=0.0,
            root_y=0.20,
            root_z=round(tail_z + length_m * 0.16, 3),
        )

        h_stab = HorizontalStabSpec(
            present=True,
            semi_span_m=round(wingspan_m * 0.20, 3),
            root_chord_m=round(length_m * 0.13, 3),
            tip_chord_m=round(length_m * 0.06, 3),
            sweep_deg=18.0 if is_fighter else 6.0,
            root_y=0.15,
            root_z=round(tail_z + length_m * 0.08, 3),
        )

        tail = TailSpec(
            configuration="conventional",
            horizontal_stabilizer=h_stab,
            vertical_fins=[v_fin],
            has_dorsal_fin=is_fighter,
            dorsal_fin_length_m=round(length_m * 0.06, 3),
        )

        propulsion = PropulsionSpec(
            type="jet_internal" if is_fighter else ("propeller_nose" if wingspan_m > 7.0 and length_m < 15.0 else "jet_internal"),
            num_blades=5 if wingspan_m >= 10.5 else 3,
            spinner_length=round(length_m * 0.08, 3),
            spinner_radius=round(max_w * 0.35, 3),
            thrustline_y=0.0,
            exhaust_z=round(tail_z, 3),
            exhaust_radius=round(max_w * 0.32, 3),
        )

        return AircraftSemanticSpec(
            aircraft_name=aircraft_name,
            aircraft_type="fighter_jet" if is_fighter else "trainer",
            wingspan_m=round(wingspan_m, 2),
            length_m=round(length_m, 2),
            height_m=round(height_m, 2),
            fuselage=fuselage,
            wings=wings,
            tail=tail,
            propulsion=propulsion,
        )
