# AirCreator 🛩️

> Plataforma inteligente para geração automatizada de modelos 3D aeronáuticos e objetos a partir de blueprints ortográficas (Front, Top, Side), com topologia estruturada em anéis de seções transversais (*stations*), auto-rigging cinemático (`.dnm`), física calibrada (`.dat`) e suporte nativo ao simulador YSFlight e padrões universais (glTF/OBJ).

---

## 📁 Estrutura do Repositório

```text
AirCreator/
├── backend/            # Engine geométrica, visão computacional e APIs em Python (FastAPI)
│   ├── app/
│   │   ├── api/        # Endpoints REST e WebSocket
│   │   ├── core/       # Configurações e utilitários globais
│   │   ├── cv/         # Módulo de visão computacional (OpenCV, extração de contornos)
│   │   ├── geometry/   # Motor de lofting paramétrico e distribuição de vértices
│   │   └── parsers/    # Parsers e geradores de .srf, .dnm, .dat e .lst
│   ├── tests/          # Testes unitários e de integração (pytest)
│   ├── pyproject.toml  # Configuração de ferramentas (ruff, pytest)
│   └── requirements.txt
├── frontend/           # Estúdio Web interativo em Next.js / Three.js
│   ├── src/
│   │   ├── app/        # Rotas da aplicação (Next.js App Router)
│   │   ├── components/ # Viewport 3D 4-quadrantes, gizmos, controles
│   │   ├── lib/        # Utilitários e manipuladores de malha no cliente
│   │   └── types/      # Tipos TypeScript para geometrias, nós DNM e aero
│   ├── package.json
│   └── tsconfig.json
└── docs/               # Especificação técnica, blueprints e modelos de referência
    ├── AIRCRAFT_CREATION_TECHNICAL_SPEC.md
    ├── blueprint.jpg
    ├── exemplo-distribuicao-vertices.jpg
    ├── resultado-3D.png
    └── t-25/
```

---

## 🚀 Guia de Desenvolvimento

### Backend (Python 3.12+)
```bash
cd backend
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
pytest
uvicorn app.main:app --reload --port 8000
```

### Frontend (Node.js 20+)
```bash
cd frontend
npm install
npm run dev
```

---

## 🛠️ Especificações Técnicas
Consulte [`docs/AIRCRAFT_CREATION_TECHNICAL_SPEC.md`](docs/AIRCRAFT_CREATION_TECHNICAL_SPEC.md) para detalhes completos sobre convenções matemáticas de mão esquerda, classes de animação cinemática (`CLA 0..31`), formato poligonal `.srf` e parâmetros aerodinâmicos `.dat`.
