# AirCreator 🛩️

> Plataforma inteligente para geração automatizada de modelos 3D aeronáuticos e objetos a partir de blueprints ortográficas (Front, Top, Side), com topologia estruturada em anéis de seções transversais (*stations*), auto-rigging cinemático (`.dnm`), física calibrada (`.dat`) e suporte nativo ao simulador YSFlight e padrões universais (glTF/OBJ).

---

## 📁 Estrutura do Repositório

```text
AirCreator/
├── backend/            # Engine geométrica, visão computacional e APIs em Python (FastAPI)
│   ├── app/
│   │   ├── api/        # Endpoints REST (/blueprint, /reconstruction, /export)
│   │   ├── core/       # Configurações globais e CORS
│   │   ├── cv/         # Módulo de visão computacional (OpenCV, eixos e calibração)
│   │   ├── geometry/   # Motor de lofting, aerofólios NACA, fatiador e rigging
│   │   ├── physics/    # Calibrador aerodinâmico, física .dat e malha de colisão
│   │   ├── parsers/    # Parsers e geradores de .srf, .dnm, .dat e .lst
│   │   └── export/     # Empacotador ZIP YSFlight, exportador OBJ e validador
│   ├── tests/          # Suíte completa com 32 testes unitários e de integração
│   ├── pyproject.toml  # Configuração de ferramentas (ruff, pytest)
│   └── requirements.txt
├── frontend/           # Estúdio Web interativo em Next.js / Three.js
│   ├── src/
│   │   ├── app/        # Rotas da aplicação (Next.js App Router)
│   │   ├── components/ # Viewport 4-quadrantes (estilo Metasequoia) e controles
│   │   ├── store/      # Zustand store com estado de animações e calibrador
│   │   └── types/      # Tipos TypeScript para geometrias, nós DNM e aero
│   ├── package.json
│   └── tsconfig.json
├── docs/               # Especificação técnica, blueprints e modelos de referência
│   ├── AIRCRAFT_CREATION_TECHNICAL_SPEC.md
│   ├── blueprint.jpg
│   ├── exemplo-distribuicao-vertices.jpg
│   ├── resultado-3D.png
│   └── t-25/
└── output/             # Arquivos gerados para teste e exportação (ignorado no git)
```

---

## 🚀 Como Modelar uma Nova Aeronave a partir de Blueprint

### Passo 1: Fornecer a Imagem da Blueprint
Coloque a imagem com as 3 vistas ortográficas (Front, Top, Side) ou utilize a API:
```bash
curl -X POST "http://localhost:8000/api/v1/blueprint/decompose" \
  -F "file=@caminho/para/nova_blueprint.jpg"
```
O algoritmo de visão computacional detectará e isolará automaticamente as vistas `top`, `front` e `side`, alinhando os eixos de simetria $X=0$, linhas d'água $Y=0$ e comprimento $Z$.

### Passo 2: Reconstrução e Rigging Automático
Gere o modelo 3D completo com superfícies de controle e física:
```bash
curl -X POST "http://localhost:8000/api/v1/reconstruction/generate-aircraft" \
  -H "Content-Type: application/json" \
  -d '{
    "blueprint_path": "docs/blueprint.jpg",
    "wingspan_m": 11.14,
    "length_m": 11.38,
    "height_m": 3.97
  }'
```

### Passo 3: Exportar Pacote Pronto para o Simulador
Baixe o arquivo `.zip` com toda a estrutura necessária para o YSFlight:
```bash
curl -X POST "http://localhost:8000/api/v1/export/ysflight-zip" \
  -H "Content-Type: application/json" \
  -d '{
    "aircraft_name": "EMB-314 Super Tucano",
    "blueprint_path": "docs/blueprint.jpg",
    "preset_name": "SUPER_TUCANO"
  }' \
  --output super_tucano_ysflight.zip
```

---

## 🛠️ APIs REST Disponíveis

| Endpoint | Método | Descrição |
| :--- | :---: | :--- |
| `/api/v1/health` | `GET` | Health check do serviço e engine de reconstrução. |
| `/api/v1/blueprint/decompose` | `POST` | Decompõe a blueprint nas vistas ortográficas (Top, Front, Side). |
| `/api/v1/blueprint/calibrate` | `POST` | Calcula fator de escala (pixels/metro) e origens de coordenadas 3D. |
| `/api/v1/reconstruction/generate-aircraft` | `POST` | Lofta a fuselagem em quads, gera asas e empenagem completa. |
| `/api/v1/export/presets` | `GET` | Retorna presets de classes de aeronaves (Treinador, Caça, Carga). |
| `/api/v1/export/validate` | `POST` | Executa o checklist de integridade geométrica e aerodinâmica. |
| `/api/v1/export/ysflight-zip` | `POST` | Gera e faz download do pacote ZIP pronto para instalação no YSFlight. |
| `/api/v1/export/obj` | `POST` | Exporta malhas e materiais nos formatos universais Wavefront OBJ + MTL. |

---

## 🧪 Executando os Testes Automatizados

O backend conta com uma suíte de 32 testes unitários e de integração de ponta a ponta:
```bash
cd backend
$env:PYTHONPATH='backend'
python -m unittest discover -s tests
```

---

## 📖 Especificação Técnica
Consulte [`docs/AIRCRAFT_CREATION_TECHNICAL_SPEC.md`](docs/AIRCRAFT_CREATION_TECHNICAL_SPEC.md) para detalhes completos sobre convenções matemáticas de mão esquerda, classes de animação cinemática (`CLA 0..31`), formato poligonal `.srf` e parâmetros aerodinâmicos `.dat`.
