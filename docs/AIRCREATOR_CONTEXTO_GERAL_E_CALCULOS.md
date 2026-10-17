# AirCreator: Manual de Arquitetura, Engenharia Matemática e Funcionamento do Sistema

---

## 1. Visão Geral do Sistema e Filosofia de Design

O **AirCreator** é um estúdio de engenharia reversa e modelagem computacional 3D aeronáutica para a geração de modelos tridimensionais físicos, paramétricos e cinemáticos a partir de desenhos técnicos ortográficos (*blueprints* / plantas de 3 vistas).

O sistema opera sob três pilares de desacoplamento:
1. **Independência de Template / Universalidade**: A geometria não se baseia em malhas estáticas pré-moldadas. Qualquer modelo (de um planador monomotor a um caça ou birreator comercial como o Boeing 737 MAX) é gerado proceduralmente por equações matemáticas de sustentação, perfis aerodinâmicos e anéis de lofting calculados em tempo real.
2. **Representação Intermediária Semântica (`AircraftSemanticSpec`)**: A extração multimodal (via **Gemini Vision API**) traduz imagens ortográficas em parâmetros físicos e geométricos padronizados (envergadura, cordas de raiz/ponta, enflechamentos, diedros, estações transversais, coordenadas de propulsão).
3. **Rigging Cinemático e Exportação de Simulador**: Toda malha gerada gera os componentes visuais WebGL (Three.js), a estrutura de articulação de superfícies de controle de voo (ailerons, profundor, leme com canais `CLA`) e a exportação física (.srf, .dnm, .dat, .lst, .obj/.mtl).

```
                      +------------------------------------------+
                      |   Entrada: Blueprint Unificada ou         |
                      |   3 Vistas Separadas (Top, Side, Front)  |
                      +------------------------------------------+
                                           |
                                           v
                      +------------------------------------------+
                      |     Gemini Vision / Extrator Semântico   |
                      |     -> AircraftSemanticSpec (JSON)       |
                      +------------------------------------------+
                                           |
                                           v
                      +------------------------------------------+
                      |       Dynamic Builder & Lofting Engine    |
                      |  1. FuselageLofter (Anéis + Quad Dome)   |
                      |  2. WingGenerator (NACA 4-Digits, tan)   |
                      |  3. Turbofan / Propeller Generator       |
                      |  4. KinematicsRigging (PartSlicer)       |
                      +------------------------------------------+
                                           |
                    +----------------------+---------------------+
                    |                                            |
                    v                                            v
     +-------------------------------+           +-------------------------------+
     |   Studio Viewer (Frontend)    |           |    Exportador Físico / YS     |
     |  - Three.js Viewports (4Q/3D) |           |  - Malhas .srf                |
     |  - Controles Cinemáticos CLA  |           |  - Hierarquia Dinâmica .dnm   |
     |  - Inspeção de Malha / Arame  |           |  - Aerodinâmica & Voo .dat    |
     +-------------------------------+           +-------------------------------+
```

---

## 2. Sistema de Coordenadas e Convenções Espaciais

O núcleo geométrico do AirCreator adota a convenção espacial aeronáutica do padrão **YSFlight (Left-Handed System)**:

* **Eixo $+X$ (Starboard / Asa Direita)**: Positivo para a direita da aeronave; negativo ($-X$) para a asa esquerda (Port).
* **Eixo $+Y$ (Dorsal / Cima)**: Positivo para cima (teto da fuselagem / cauda vertical); negativo ($-Y$) para baixo (barriga / solo).
* **Eixo $+Z$ (Longitudinal / Frente)**: Positivo apontando para o nariz / bordo de ataque; negativo ($-Z$) apontando para a cauda / bordo de fuga.

### Mapeamento WebGL / Three.js (Right-Handed)
No frontend, para manter a orientação visual consistente:
$$(x, y, z)_{\text{three}} = (x, y, -z)_{\text{ys}} \quad \text{ou} \quad (-x, y, z)$$
Ajustado com `DoubleSide` e vetores de iluminação adequados para não inverter as normais dos polígonos.

---

## 3. Formulação Matemática dos Cálculos Geométricos

### 3.1. Asas e Superfícies Sustentadoras (`wing_generator.py`)

#### Cálculo de Perfil Aerodinâmico NACA 4-Dígitos (Simétrico NACA 00xx)
Dado o comprimento da corda local $c$ e a espessura percentual máxima $t = \text{thickness\_ratio}$ (ex: $0.12$ para $12\%$):
Para $x \in [0, c]$, a meia-espessura $y_t(x)$ é calculada pela equação analítica:
$$y_t(x) = 5 t c \left[ 0.2969\sqrt{\frac{x}{c}} - 0.1260\left(\frac{x}{c}\right) - 0.3516\left(\frac{x}{c}\right)^2 + 0.2843\left(\frac{x}{c}\right)^3 - 0.1015\left(\frac{x}{c}\right)^4 \right]$$

#### Distribuição Spanwise com Enflechamento e Diedro
Para uma estação ao longo da envergadura com fração adimensional $\eta \in [0, 1]$ e posição lateral $s = \eta \cdot b_{\text{painel}}$:
* **Deslocamento Longitudinal (Enflechamento)**:
  Utiliza rigorosamente a tangente do ângulo de bordo de ataque $\Lambda_{\text{LE}}$:
  $$z_{\text{estação}} = z_{\text{raiz}} - s \cdot \tan(\Lambda_{\text{LE}})$$
  *(Nota crítica: O uso de $\sin(\Lambda)$ subestima o enflechamento em até $25\%$, o correto é $\tan(\Lambda)$).*
* **Deslocamento Vertical (Diedro $\Gamma$)**:
  $$y_{\text{estação}} = y_{\text{raiz}} + s \cdot \sin(\Gamma)$$
* **Deslocamento Lateral**:
  $$x_{\text{estação}} = \pm (x_{\text{raiz}} + s)$$

#### Quebra no Bordo de Fuga (Yehudi Kink)
Para aeronaves de transporte comercial, o bordo de fuga interno é reto até a posição do motor antes de afilar. O sistema utiliza uma distribuição bilinear de corda controlada por $\eta_{\text{kink}}$:
$$c(\eta) = \begin{cases} 
c_{\text{raiz}} + \frac{\eta}{\eta_{\text{kink}}} (c_{\text{kink}} - c_{\text{raiz}}), & \eta \le \eta_{\text{kink}} \\
c_{\text{kink}} + \frac{\eta - \eta_{\text{kink}}}{1 - \eta_{\text{kink}}} (c_{\text{ponta}} - c_{\text{kink}}), & \eta > \eta_{\text{kink}}
\end{cases}$$
Onde $c_{\text{kink}} = c_{\text{raiz}} - (\eta_{\text{kink}} \cdot b_{\text{painel}} \cdot \tan(\Lambda_{\text{LE}}))$, garantindo que o bordo de fuga entre $\eta = 0$ e $\eta = \eta_{\text{kink}}$ seja estritamente perpendicular à linha de centro ($Z_{\text{TE}} = \text{constante}$).

---

### 3.2. Lofting de Fuselagem e Radome sem Vértice Cônico (`fuselage_lofter.py`)

#### Seções Transversais Elípticas / Super-Elípticas
Cada estação $i$ define um anel com $m$ vértices (padrão $m=24$):
$$\theta_j = \frac{2\pi j}{m}, \quad j \in \{0, \dots, m-1\}$$
$$v_x(j) = r_x \sin(\theta_j)$$
$$v_y(j) = y_c + r_y \cos(\theta_j)$$
$$v_z(j) = z_{\text{estação}}$$

#### Radome Elipsoidal Multi-Anel com Fechamento 100% Quadrilátero
Para evitar o defeito clássico de "vértice em agulha / cone pontiagudo", o nariz projeta $K=3$ anéis esferoidais à frente da estação 0 parametrizados por latitude $\phi \in [0, \pi/2]$:
$$z_k = z_0 + L_{\text{dome}} \sin(\phi_k)$$
$$r_{x,k} = r_{0x} \cos(\phi_k)$$
$$r_{y,k} = r_{0y} \cos(\phi_k)$$
$$y_{c,k} = y_{0c} - (0.35 \cdot r_{0y}) \sin(\phi_k) \quad \text{(Caimento aerodinâmico / droop do queixo)}$$

O fechamento final do anel de ponta (raio $< 10\%$ da fuselagem) é feito por uma esteira de faces quadriláteras ($m/2 - 1$ quads), garantindo normais externas positivas em $+Z$ com zero vértices centrais de convergência e zero faces triangulares.

---

### 3.3. Motores Turbofan e Pilones de Suspensão (`dynamic_builder.py`)

As naceles de motores birreatores comerciais (ex: CFM LEAP-1B) são modeladas com:
1. **Anel de Labro (Inlet Lip)** metálico e boca de admissão com espessura aerodinâmica.
2. **Carenagem de Fan e Reversor**: Anéis cilíndricos com afunilamento em direção ao bocal de exaustão primário.
3. **Cone de Nariz Interno e Spinner**: Disco giratório com ogiva de centro.
4. **Bocal e Cone de Escape do Núcleo Quente**: Cone traseiro com coloração térmica escurecida.
5. **Pilone Cantilever Integrado**: Estrutura sólida que conecta a coroa da nacele diretamente ao intradorso e bordo de ataque da asa:
   $$z_{\text{pilone, fwd}} = z_{\text{LE}(\text{asa})}, \quad z_{\text{pilone, aft}} = z_{\text{LE}(\text{asa})} - 0.70 \cdot c_{\text{local}}$$
   Elimina qualquer folga ou suspensão desconectada entre o motor e a asa.

---

### 3.4. Fatiador e Cinemática de Superfícies de Controle (`part_slicer.py`, `kinematics_rigging.py`)

O `PartSlicer` divide superfícies estruturais em partes fixas e partes articuladas móveis sem perda de faces (técnica *Water-Tight Zero Face Loss*):
* **Identificação de Hinge**: Vértices com coordenada $z \le z_{\text{hinge}}$ e dentro do intervalo spanwise $[s_{\text{min}}, s_{\text{max}}]$ são direcionados à malha móvel.
* **Canais de Simulação (YSFlight CLA)**:
  * **CLA 7 (Ailerons)**: Estados rotacionais anti-simétricos (+Pitch na direita, -Pitch na esquerda para rolamento).
  * **CLA 6 (Profundor / Elevator)**: Estados simétricos em torno do eixo transversal $X$ centrado em $(0.0, y_{\text{hinge}}, z_{\text{hinge}})$.
  * **CLA 8 (Leme / Rudder)**: Rotação em torno do eixo vertical $Y$ de guinada.
  * **CLA 18/3 (Hélice / Propeller)**: Rotação axial contínua em torno de $Z$.

---

## 4. Estrutura de Arquivos e Código do Projeto

```
AirCreator/
├── backend/
│   ├── app/
│   │   ├── ai/
│   │   │   ├── spec.py                  # Schemas Pydantic (AircraftSemanticSpec)
│   │   │   └── gemini_extractor.py      # Extração multimodal Gemini Vision + Heurística
│   │   ├── api/
│   │   │   └── endpoints/
│   │   │       ├── reconstruction.py    # Rotas POST /upload-views e /generate-aircraft
│   │   │       ├── export.py            # Rotas de download (.srf, .dnm, .dat, .obj)
│   │   │       └── blueprint.py         # Calibração e decomposição de imagens
│   │   ├── cv/
│   │   │   ├── processor.py             # Processamento OpenCV e recorte de vistas
│   │   │   └── calibrator.py            # Escala geométrica (pixels por metro)
│   │   ├── geometry/
│   │   │   ├── wing_generator.py        # Perfis NACA, enflechamento tan(), diedro, kink
│   │   │   ├── fuselage_lofter.py       # Lofting por anéis, radome elipsoidal quad
│   │   │   ├── dynamic_builder.py       # Integração semântica de todos os componentes
│   │   │   ├── part_slicer.py           # Slicing de ailerons, profundores e lemes
│   │   │   ├── kinematics_rigging.py    # Construção do grafo de cena DynaModel
│   │   │   └── mesh_ops.py              # Fusão, normais, cálculo de área de planta
│   │   ├── parsers/
│   │   │   ├── srf.py                   # Parser e gerador de malhas .srf
│   │   │   └── dnm.py                   # Parser e serializador de arquivos .dnm
│   │   └── physics/
│   │       └── aero_calculator.py       # Cálculo de aerodinâmica, CL, CD0 e .dat
│   └── tests/                           # 36 testes automatizados de integração geométrica
├── frontend/
│   ├── src/
│   │   ├── components/studio/
│   │   │   ├── FourQuadrantStudio.tsx   # Painel com 4 quadrantes sincronizados
│   │   │   ├── PerspectiveViewport.tsx  # Câmera 3D orbital Three.js
│   │   │   ├── OrthographicViewport.tsx # Vistas ortográficas (Top, Front, Side)
│   │   │   ├── BlueprintUploadModal.tsx # Upload de 3 vistas ou folha unificada
│   │   │   ├── HierarchySidebar.tsx     # Árvore de componentes e visibilidade
│   │   │   └── AnimationControlPanel.tsx# Sliders para teste cinemático das superfícies
│   │   ├── lib/
│   │   │   └── threeMeshBuilder.ts      # Conversão de malhas para Three.js BufferGeometry
│   │   └── store/
│   │       └── studioStore.ts           # Gerenciamento de estado global (Zustand)
└── docs/                                # Documentação técnica, blueprints e referências
```

---

## 5. Fluxo de Execução Ponta a Ponta

1. **Upload**: O usuário fornece 3 imagens ortográficas separadas (Top, Side, Front) ou uma folha com as 3 vistas conjuntas.
2. **Análise de Visão Multimodal**: A imagem é processada pela API Gemini Vision, instruída pelas regras de aeronáutica de `gemini_extractor.py`. O retorno é um JSON validado estritamente por `AircraftSemanticSpec`.
3. **Construção Geométrica Procedural**:
   * A fuselagem gera anéis circulares/elípticos e o domo contínuo sem ponta.
   * As asas são posicionadas de acordo com a configuração de asa baixa/alta, aplicando corda com quebra Yehudi e diedro.
   * Motores turbofans ou hélices são acoplados nas coordenadas relativas.
   * O empenamento traseiro (estabilizadores bilaterais e leme) é montado na cauda.
4. **Cinemática e Rigging**: O `PartSlicer` fatia os bordos de fuga para extrair ailerons esquerdo/direito, profundores esquerdo/direito e leme, criando a hierarquia com canais CLA.
5. **Visualização em Tempo Real**: Os dados chegam ao frontend via JSON, montados diretamente em cena Three.js com suporte a wireframe, materiais metálicos e animação contínua dos controles de voo.
6. **Exportação**: O usuário pode exportar o pacote pronto para voo no YSFlight (`.srf`, `.dnm`, `.dat`, `.lst`) ou malha padrão universal (`.obj` + `.mtl`).
