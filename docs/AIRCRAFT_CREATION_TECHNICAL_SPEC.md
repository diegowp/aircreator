# Especificação Técnica de Criação e Modelagem de Aeronaves YSFlight
## Guia de Engenharia e Arquitetura para Ferramentas de Autoria e Modelagem

Este documento descreve detalhadamente todos os padrões, convenções matemáticas, estruturas de arquivos e regras de física necessários para construir uma **ferramenta de criação de novos modelos de avião** compatíveis com o ecossistema do simulador **YSFlight**.

---

## Sumário
1. [Visão Geral e Arquitetura de Arquivos](#1-visão-geral-e-arquitetura-de-arquivos)
2. [Sistema de Coordenadas, Eixos e Unidades Matemáticas](#2-sistema-de-coordenadas-eixos-e-unidades-matemáticas)
3. [Formato de Malha Poligonal 3D (.srf)](#3-formato-de-malha-poligonal-3d-srf)
4. [Grafo de Cena, Hierarquia e Cinemática (.dnm)](#4-grafo-de-cena-hierarquia-e-cinemática-dnm)
5. [Tabela Completa de Canais de Animação (CLA 0 a CLA 31)](#5-tabela-completa-de-canais-de-animação-cla-0-a-cla-31)
6. [Especificação de Física, Voo e Engenharia (.dat)](#6-especificação-de-física-voo-e-engenharia-dat)
7. [Manifesto e Registro no Simulador (.lst)](#7-manifesto-e-registro-no-simulador-lst)
8. [Arquitetura Recomendada para a Ferramenta de Criação](#8-arquitetura-recomendada-para-a-ferramenta-de-criação)
9. [Checklist de Validação e Exportação](#9-checklist-de-validação-e-exportação)

---

## 1. Visão Geral e Arquitetura de Arquivos

Uma aeronave no YSFlight é composta por um conjunto desacoplado de arquivos ASCII organizados dentro de um subdiretório dedicado:

```text
meu_aviao/
├── meu_aviao.lst          # Manifesto de declaração de arquivos
├── meu_aviao.dnm          # Grafo de cena 3D, cinemática das partes móveis e malhas PCK
├── meu_aviao.dat          # Ficha técnica aeronáutica, física, pesos, aerodinâmica e armas
├── meu_aviao_coll.srf     # Malha simplificada de colisão física (opcional, recomendada)
├── cockpit.srf            # Malha 3D da cabine interna para visão PILOT em 1ª pessoa (opcional)
├── wing_left.srf          # Arquivos de malha externos referenciados via FIL (opcional)
├── wing_right.srf         # ...
└── sounds/                # Amostras de áudio WAVE (motor, pós-combustor, toque de trem)
```

### Papel de Cada Arquivo no Ciclo de Vida:
* **`.lst` (List / Manifesto)**: Arquivo inicial apontado pelo catálogo do simulador (`aircraft.lst`). Ele especifica quais arquivos `.dat` e `.dnm` devem ser carregados para instanciar a aeronave.
* **`.dnm` (DynaModel)**: Grafo hierárquico orientado a objetos que define os nós de peças (`SRF`), pontos de articulação (`CNT`), herança pai-filho (`REL` e `CLD`), canais de animação cinemática (`CLA`) e blocos embutidos de geometria compactada (`PCK`).
* **`.srf` (Surface)**: Malha 3D poligonal contendo vértices, faces planas com iluminação faceted ou Gouraud (`R`), cores 15/24 bits e transparências (`ZA`).
* **`.dat` (Data / Flight Dynamics)**: Define a física do modelo: propulsão (empuxo a jato ou hélice/pistão), aerodinâmica (polarares de sustentação $C_L$, arrasto $C_D$, estol), limites operacionais, massas e pontos de contato tridimensionais (trens de pouso, visão do piloto, fumaça).

---

## 2. Sistema de Coordenadas, Eixos e Unidades Matemáticas

O YSFlight utiliza um **Sistema de Coordenadas de Mão Esquerda (Left-Handed System)**. Compreender esse sistema é fundamental para qualquer ferramenta de autoria, pois ele diverge do padrão comum do Three.js, Blender ou OpenGL (que utilizam a regra da mão direita).

### 2.1 Eixos Espaciais
* **Eixo $+X$ (Direita / Starboard)**: Positivo apontando para a asa direita; negativo para a asa esquerda (Port).
* **Eixo $+Y$ (Para Cima / Dorsal)**: Positivo apontando para o teto/dorsal do avião; negativo para a barriga/chão.
* **Eixo $+Z$ (Para Frente / Longitudinal)**: Positivo apontando para o nariz do avião; negativo para a cauda.

```text
                +Y (Cima / Dorsal)
                 ^
                 |   +Z (Frente / Nariz)
                 |  /
                 | /
 -X (Asa Esq) <--+--> +X (Asa Dir)
                /
               /
             -Z (Cauda)
```

### 2.2 Unidades de Medida
* **Distâncias lineares**: Sempre em **metros** ($1.0 = 1\text{m}$).
  * *Observação de compatibilidade*: O parser suporta sufixos como `ft` ($1\text{ft} = 0.3048\text{m}$) e `in` ($1\text{in} = 0.0254\text{m}$).
* **Massas**: Sempre em **toneladas métricas** ($1.0 = 1000\text{kg}$).
  * *Sufixos suportados*: `kg` ($1\text{kg} = 0.001\text{t}$) e `lb` ($1\text{lb} \approx 0.000453592\text{t}$).
* **Forças e Empuxo**: Quilogramas-força ou Newtons conforme a chave (`kg` padrão para empuxo estático no `.dat`).

### 2.3 Unidades Angulares de 16 Bits
O YSFlight codifica todos os ângulos internos do arquivo `.dnm` e atitudes em **inteiros de 16 bits**, onde uma volta completa ($360^\circ$) corresponde exatamente a $65536$ unidades angulares:

$$\theta_{\text{graus}} = \frac{\theta_{16} \times 360}{65536} \approx \frac{\theta_{16}}{182.0444}$$

$$\theta_{\text{rad}} = \theta_{16} \times \frac{\pi}{32768}$$

| Ângulo em Graus | Valor Inteiro YSFlight (16-bit) | Hexadecimal |
| :---: | :---: | :---: |
| $0^\circ$ | `0` | `0x0000` |
| $+45^\circ$ | `8192` | `0x2000` |
| $+90^\circ$ | `16384` | `0x4000` |
| $+180^\circ$ | `32768` ou `-32768` | `0x8000` |
| $-90^\circ$ ($270^\circ$) | `-16384` ou `49152` | `0xC000` |

### 2.4 Ordem de Rotação de Atitude (Heading, Pitch, Bank)
A rotação de orientação espacial é definida pela trinca `(h, p, b)`:
1. **Heading ($h$)**: Rotação em torno do eixo $Y$ (plano $XZ$), no sentido horário olhando de cima: `RotateXZ(h)`.
2. **Pitch ($p$)**: Rotação em torno do eixo $X$ (plano $ZY$): `RotateZY(p) = RotateYZ(-p)`.
3. **Bank / Roll ($b$)**: Rotação em torno do eixo $Z$ (plano $XY$): `RotateXY(b)`.

A matriz de rotação total acumulada é estritamente avaliada como:
$$M = R_{XZ}(h) \cdot R_{ZY}(p) \cdot R_{XY}(b)$$

### 2.5 Mapeamento Matemático para Three.js / WebGL / OpenGL
Para renderizar ou manipular malhas YSFlight em um motor padrão de mão direita (Right-Handed):
* Transformação de vértice: $(x, y, z)_{ys} \to (-x, y, z)_{three}$.
* Matriz de transformação: Seja $S = \text{diag}(-1, 1, 1, 1)$. A matriz no Three.js é obtida por conjugação de similaridade:
$$M_{\text{three}} = S \cdot M_{ys} \cdot S$$

---

## 3. Formato de Malha Poligonal 3D (.srf)

O formato `.srf` (Surface) é um formato de texto ASCII conciso otimizado para renderização de superfícies poligonais com iluminação por face ou suavização Gouraud.

### 3.1 Estrutura Sintática
```text
SURF
V <x> <y> <z> [R]
V <x> <y> <z> [R]
...
F
C <r> <g> <b>
N <cx> <cy> <cz> <nx> <ny> <nz>
V <idx0> <idx1> <idx2> ...
[B]
E
...
ZA <polyIdx> <alpha> ...
ZL <polyIdx> ...
E
```

### 3.2 Comandos e Diretivas
| Comando Curto | Comando Longo | Descrição e Parâmetros |
| :--- | :--- | :--- |
| `SURF` | `SURF` | Início do bloco de geometria de superfície. |
| `V` | `VER` | Declaração de vértice: `V <x> <y> <z> [R]`. Se `R` estiver presente, indica **Round Shading** (a normal do vértice será calculada pela média das faces vizinhas para sombreamento suave). |
| `F` | `FAC` | Inicia a definição de uma face/polígono. |
| `C` | `COL` | Cor da face: pode ser `C <r> <g> <b>` (RGB 0..255) ou `C <int15>` (cor embutida de 15 bits). |
| `N` | `NOR` | Vetor normal e centro da face: `N <cx> <cy> <cz> <nx> <ny> <nz>` ou resumido `N <nx> <ny> <nz>`. |
| `V` (na face) | `VER` | Lista de índices de vértices que formam o polígono (índices iniciados em `0`). Devem estar em ordem anti-horária (*counter-clockwise*) vista de fora. |
| `B` | `BRI` | **Bright / Unshaded**: polígono auto-iluminado (ignora a luz solar, útil para telas de instrumentos, janelas iluminadas ou chamas). |
| `E` | `END` | Encerra a definição do polígono atual ou do bloco `SURF`. |
| `ZA` | `ZA` | Transparência Alfa pós-malha: `ZA <polyIdx> <alpha0..255> <polyIdx2> <alpha2>...`. |
| `ZL` | `ZL` | Luz pontual / Sprite luminoso (*Light sprite*): `ZL <polyIdx>...`. |

### 3.3 Codificação de Cores em 15-Bit
Muitos modelos históricos do YSFlight utilizam inteiros compactos de 15 bits no comando `C <int15>`. A conversão exata do motor oficial C++ (`ysgeometry.h`) para RGB 24-bit é:

```typescript
function color15ToRgb(c15: number): [number, number, number] {
  const g5 = (c15 >> 10) & 31;
  const r5 = (c15 >> 5) & 31;
  const b5 = c15 & 31;

  const r = Math.round((r5 * 255) / 31);
  const g = Math.round((g5 * 255) / 31);
  const b = Math.round((b5 * 255) / 31);

  return [r, g, b];
}

function rgbToColor15(r: number, g: number, b: number): number {
  const r5 = Math.round((r * 31) / 255);
  const g5 = Math.round((g * 31) / 255);
  const b5 = Math.round((b * 31) / 255);

  return (g5 << 10) | (r5 << 5) | b5;
}
```

---

## 4. Grafo de Cena, Hierarquia e Cinemática (.dnm)

O arquivo `.dnm` (DynaModel) é o coração articulado da aeronave. Ele reúne as malhas 3D e define a árvore de dependência de peças móveis.

### 4.1 Cabeçalho e Pacotes PCK
```text
DNMVER 1

PCK asa_esquerda.srf 142
SURF
V -0.5 0.2 1.2
...
E

PCK aileron_esq.srf 48
SURF
...
E
```
* `PCK <nome_malha.srf> <total_de_linhas>`: Embute o arquivo `.srf` diretamente dentro do `.dnm`, dispensando dezenas de arquivos avulsos na pasta. O número indica quantas linhas de texto após o `PCK` pertencem àquela malha.

### 4.2 Nós de Peças (Nós SRF)
Cada componente articulado ou estático da aeronave é declarado como um nó:

```text
SRF "asa_esquerda"
FIL asa_esquerda.srf
CLA 0
NST 0
POS 0.0 0.0 0.0 0 0 0 1
CNT 0.0 0.0 0.0
REL DEP
CLD "aileron_esq"
END

SRF "aileron_esq"
FIL aileron_esq.srf
CLA 7
NST 3
POS 0.0 0.0 0.0 0 0 0 1
CNT -3.20 -0.15 -1.10
REL DEP
STA 0.0 0.0 0.0 0 0 0 1
STA 0.0 0.0 0.0 0 3641 0 1
STA 0.0 0.0 0.0 0 -3641 0 1
END
```

### 4.3 Diretivas de Nó
| Diretiva | Parâmetros | Descrição |
| :--- | :--- | :--- |
| `SRF "<nome>"` | String | Nome de identificação do nó (ex: `"fuselage"`, `"gear_front"`). |
| `FIL <arquivo>` | String | Nome do `.srf` associado. O motor procura primeiro nos blocos `PCK` internos; se não encontrar, busca um arquivo `.srf` externo no diretório. |
| `POS` | `<x> <y> <z> <h> <p> <b> [vis]` | Translação e atitude estática de montagem da peça. `vis=1` (visível) ou `0` (oculto). |
| `CNT` | `<x> <y> <z>` | **Centro / Pivô de Rotação**. Todas as rotações angulares dos estados `STA` ocorrerão em torno deste ponto. |
| `REL` | `DEP` ou `IND` | `DEP`: Nó dependente (herda a matriz de transformação do pai). `IND`: Nó independente (ignora o pai). |
| `CLD "<filho>"` | String | Declara um nó filho. Deve haver uma diretiva `CLD` para cada filho. |
| `CLA <canal>` | Inteiro (0..31) | **Classe de Animação Cinemática** controlada pelo simulador. |
| `NST <qtd>` | Inteiro | Número de estados de animação declarados no nó. |
| `STA` | `<dx> <dy> <dz> <dh> <dp> <db> [vis]` | Vetor delta de deslocamento, rotação angular em 16 bits e visibilidade do estado. |
| `END` | - | Finaliza a declaração do nó. |

### 4.4 Equação Geral de Transformação de um Nó SRF
Para calcular a matriz de um nó em tempo de execução, dado o pivô `CNT`, o offset estático `POS` e o delta animado interpolado do estado `STA`:

$$M_{\text{local}} = T(\text{pos}) \cdot R(\text{att}) \cdot T(\text{cnt}) \cdot R(\Delta\text{att}) \cdot T(\Delta\text{pos}) \cdot T(-\text{cnt})$$

$$M_{\text{mundo}} = M_{\text{pai}} \cdot M_{\text{local}}$$

---

## 5. Tabela Completa de Canais de Animação (CLA 0 a CLA 31)

Qualquer ferramenta de modelagem precisa saber quais classes de animação atribuir a cada peça:

| Classe (`CLA`) | Designação Aeronáutica | Estados (`NST`) | Descrição da Cinemática e Interpolação |
| :---: | :--- | :---: | :--- |
| **`0`** | Trem de Pouso Principal / Geral | 2 | `STA 0`: Recolhido; `STA 1`: Baixado. Interpola linearmente de $0.0$ a $1.0$ durante o recolhimento/abaixamento. |
| **`1`** | Asa de Geometria Variável (VGW) / Hélice Alternativa | 2 | Em caças com asas de enflechamento variável (F-14, Mirage G): `STA 0` aberta, `STA 1` enflechada. Em turboélices (EMB-111): comuta entre pás estáticas e disco translúcido. |
| **`2`** | Pós-Combustor (*Afterburner / Reheat*) | 2 | `STA 0`: Chama apagada (`vis=0`); `STA 1`: Chama ativa (`vis=1`). Ativado quando a manete passa de $100\%$ de empuxo militar. |
| **`3`** | Rotação Contínua da Hélice / Rotor Principal | 2 | Eixo rotativo contínuo em torno do pivô `CNT`. O simulador incrementa o ângulo continuamente proporcionalmente ao RPM do motor. |
| **`4`** | Freios Aerodinâmicos / *Spoilers* | 2 | `STA 0`: Fechado; `STA 1`: Abertura plena. Interpola com o acionamento do freio de ar. |
| **`5`** | *Flaps* de Sustentação | 2 | `STA 0`: Flap recolhido ($0^\circ$); `STA 1`: Flap em extensão máxima de pouso (típico $35^\circ$ a $45^\circ$). |
| **`6`** | Profundor (*Elevator* — Pitch) | 3 | **3 Estados**: `STA 0`: Neutro ($0^\circ$); `STA 1`: Cabrar (manche para trás, deflexão para cima); `STA 2`: Picar (manche para frente, deflexão para baixo). |
| **`7`** | Ailerons (Rolamento / Roll) | 3 | **3 Estados**: `STA 0`: Neutro; `STA 1`: Comando para a direita; `STA 2`: Comando para a esquerda. Peças esquerdas e direitas devem ter deltas angulares invertidos. |
| **`8`** | Leme de Direção (*Rudder* — Yaw) | 3 | **3 Estados**: `STA 0`: Neutro; `STA 1`: Guinada para a direita; `STA 2`: Guinada para a esquerda. |
| **`9`** | Baia Interna de Armas / Rampa de Carga | 2 | `STA 0`: Portas fechadas; `STA 1`: Portas abertas para lançamento de mísseis/bombas ou rampa aberta. |
| **`10`** | Portas Deslizantes / Faróis / Tubeira | 2 | Portas corrediças de helicópteros (S-70, UH-1H), faróis escamoteáveis ou vetorização básica de empuxo. |
| **`11`** | Paraquedas de Frenagem (*Drag Chute*) | 2 | `STA 0`: Guardado no casulo de cauda (`vis=0`); `STA 1`: Aberto e enfunado na cauda (`vis=1`). |
| **`14`** | Portas Internas do Trem de Pouso | 2 | **Ciclo Temporário Trifásico**: Abre quando o trem sai do casulo ($0.0 \to 0.2$), permanece aberta durante o trânsito ($0.2 \to 0.8$), e **fecha novamente com o trem travado embaixo** ($0.8 \to 1.0$). |
| **`15`** | Portas Secundárias do Trem (*Gear Bay*) | 2 | Abre progressivamente no primeiro terço de curso do trem ($0.0 \to 0.6$). |
| **`16`** | Gancho de Parada Naval (*Tailhook*) | 2 | `STA 0`: Recolhido na fuselagem inferior; `STA 1`: Abaixado a $\approx 45^\circ$ para retenção em cabos de porta-aviões. |
| **`17`** | Portas Rápidas do Trem | 2 | Abertura ultrarrápida entre $0.0$ e $0.2$, permanecendo aberta enquanto o trem estiver embaixo. |
| **`18`** | Pás de Hélice Sólidas (Baixa Rotação / Solo) | 2 | Visível com motor cortado ou em marcha lenta ($\le 30\%$). Ocultado em alta potência. |
| **`19`** | Trem Traseiro / Secundário Independente | 2 | Usado em trens auxiliares retráteis independentes (ex: pontas de asa de Harrier ou B-52). |
| **`20`** | Disco Translúcido de Hélice (Alta Rotação / Voo) | 2 | Disco com textura ou cores transparentes (`ZA`). Invisível em marcha lenta; visível em regimes de alta potência ($> 30\%$). |
| **`31`** | Bequilha Direcional (*Nosewheel Steering*) | 3 | Articulação do trem de pouso dianteiro comandada pelos pedais de leme no solo (sincronizada com CLA 8). |

---

## 6. Especificação de Física, Voo e Engenharia (.dat)

O arquivo `.dat` é composto por linhas chave-valor no formato:
`CHAVE VALOR [VALOR2 ...]`

Abaixo está o dicionário completo de todas as propriedades exigidas e opcionais:

### 6.1 Identificação e Radar
* `IDENTIFY "<Nome do Avião>"`: Nome de exibição oficial nos menus e HUD.
* `CATEGORY <FIGHTER|NORMAL|CARGO|HELICOPTER>`: Categoria de IA e comportamento operacional.
* `AIRCLASS <AIRPLANE|HELICOPTER>`: Define as leis de controle aerodinâmico e vetor sustentador primário.
* `STRENGTH <int>`: Pontos de vida estruturais (T-25: `2`, Caças: `10–25`, Bombardeiros: `40–80`).
* `RADARCRS <float>m^2`: Seção de eco radar (RCS). Aeronaves furtivas: `0.001` a `0.05`; caças padrão: `1.0` a `5.0`; aviões de carga: `20.0` a `50.0`.

### 6.2 Propulsão e Motores

#### Motores a Jato (Turbofans / Turbojatos):
* `THRMILIT <força>`: Empuxo militar máximo (seco) sem pós-combustão. Ex: `15000kg` ou `147000N`.
* `THRAFTBN <força>`: Empuxo com pós-combustor pleno. Se ausente, o avião não possui pós-combustor.
* `FUELMILI <taxa>kg/sec`: Consumo horário em regime militar (típico: `0.5` a `3.5 kg/s`).
* `FUELABRN <taxa>kg/sec`: Consumo com pós-combustão ativa (típico: `3.0` a `15.0 kg/s`).
* `THRVREFC <float>`: Eficiência do reversor de empuxo ($0.0$ a $0.8$).
* `TRSTVCTR <TRUE|FALSE>`: Habilita tubeiras de empuxo vetorado (Super-manobrabilidade).
* `PSTMPTCH <graus>`, `PSTMYAW_ <graus>`, `PSTMROLL <graus>`: Autoridade de controle além do estol.

#### Motores a Pistão / Turboélices:
* `PROPELLR <potência>HP`: Potência nominal no eixo (ex: `260HP` no T-25; `1200HP` no Tucano).
* `PROPEFCY <float>`: Eficiência mecânica da hélice (típico: `0.75` a `0.85`).
* `PROPVMIN <float>m/s`: Velocidade mínima de fluxo para tração estática eficiente (típico: `10` a `20 m/s`).

### 6.3 Pesos e Balanceamento
* `WEIGHCLN <peso>`: Peso limpo (vazio estrutural sem combustível nem armas). Ex: `0.95t` ou `950kg`.
* `WEIGFUEL <peso>`: Capacidade máxima interna de combustível. Ex: `0.17t` ou `170kg`.
* `WEIGLOAD <peso>`: Carga paga máxima permitida (armas, pods, passageiros). Ex: `0.30t`.
* `INITFUEL <porcentagem>%`: Porcentagem inicial de combustível no spawn (ex: `100%`).
* `INITLOAD <peso>`: Carga útil inicial padrão ao iniciar o voo.

$$\text{MTOW (Peso Máximo de Decolagem)} = \text{WEIGHCLN} + \text{WEIGFUEL} + \text{WEIGLOAD}$$

### 6.4 Aerodinâmica e Superfícies Alares
* `WINGAREA <área>m^2`: Área alar de referência em metros quadrados (determina a sustentação base $L = \frac{1}{2}\rho V^2 S C_L$).
* `CRITAOAP <graus>`: Ângulo de ataque crítico de estol positivo (típico: `+14` a `+18` graus).
* `CRITAOAM <graus>`: Ângulo de ataque crítico de estol negativo (típico: `-10` a `-14` graus).
* `CRITSPED <velocidade>`: Velocidade crítica compressível / Mach crítico (ex: `0.85MACH` ou `450kt`).
* `MAXSPEED <velocidade>`: Velocidade estrutural máxima nunca exceder $V_{NE}$ (ex: `0.95MACH` ou `550kt`).
* `MANESPD1 <velocidade>`: Velocidade mínima de manobra ágil (típico: velocidade de decolagem $+ 15\%$).
* `MANESPD2 <velocidade>`: Velocidade de manobra plena de combate sem estol induzido por carga G.

#### Coeficientes Incrementais de Superfícies Móveis:
* `CLBYFLAP <float>`: Incremento no coeficiente de sustentação ($\Delta C_L$) ao baixar flaps (típico: `0.2` a `0.5`).
* `CDBYFLAP <float>`: Arrasto parasita induzido pelos flaps ($\Delta C_D$, típico: `0.1` a `0.3`).
* `CDBYGEAR <float>`: Arrasto de forma do trem de pouso estendido ($\Delta C_D$, típico: `0.2` a `0.5`).
* `CDBYSPOI <float>`: Arrasto massivo gerado pelos spoilers/speedbrakes (típico: `0.5` a `1.2`).
* `VARGEOMW <TRUE|FALSE>`: Declara se a asa possui geometria variável.
* `CLVARGMW <float>`, `CDVARGMW <float>`: Variações de $C_L$ e $C_D$ com asas enflechadas.

#### Constantes de Estabilidade e Amortecimento Dinâmico:
* `CPITMANE <float>`: Manobrabilidade em arfagem (Pitch rate authority: `3.0` a `12.0`).
* `CPITSTAB <float>`: Estabilidade estática longitudinal / amortecimento de arfagem (`4.0` a `15.0`).
* `CROLLMAN <float>`: Taxa de rolamento por aileron (Roll rate: `2.0` a `8.0`).
* `CYAWMANE <float>`: Autoridade de guinada por leme de direção (`2.0` a `6.0`).
* `CYAWSTAB <float>`: Estabilidade direcional / efeito cata-vento de cauda (`4.0` a `10.0`).

### 6.5 Pontos Tridimensionais de Contato e Marcadores Visuais
Os pontos utilizam coordenadas no sistema YSFlight `(X, Y, Z)` em metros:

* `LEFTGEAR <x> <y> <z>`: Ponto de contato do pneu principal esquerdo no solo ($X < 0$, $Y$ negativo).
* `RIGHGEAR <x> <y> <z>`: Ponto de contato do pneu principal direito no solo ($X > 0$, $Y$ negativo).
* `WHELGEAR <x> <y> <z>`: Ponto de contato da bequilha (ou roda de nariz) no solo ($X \approx 0$).
* `COCKPITP <x> <y> <z>`: Posição exata dos olhos do piloto para a câmera interna de 1ª pessoa.
* `HTRADIUS <raio>m`: Raio da esfera externa de colisão física contra o terreno e outras aeronaves.
* `SMOKEGEN <x> <y> <z>`: Ponto de ejeção de fumaça acrobática de cauda ou asa.
* `VAPORPO0 <x> <y> <z>` e `VAPORPO1 <x> <y> <z>`: Pontas de asa esquerda e direita para geração do efeito de condensação por vórtice em curvas de alta carga G.
* `EXCAMERA "<Nome>"` seguido de `CAMERAPO <x> <y> <z>` e `CAMERADR <h> <p> <b>`: Câmeras extras personalizáveis (ex: visão de bordo de asa, baia de bombas).

```text
               Nariz (+Z)
                   |
             [ WHELGEAR ]  (0.0, -1.70, 1.85)
                   |
                   |
   [ LEFTGEAR ]----+----[ RIGHGEAR ]
 (-1.35, -1.72, -0.40)   (+1.35, -1.72, -0.40)
                   |
               Cauda (-Z)
```

### 6.6 Armamentos e Aviônica
* `INITGUN_ <balas>`: Munição inicial do canhão interno (ex: `500`).
* `GUNPOWER <dano>`: Dano por projétil de 20mm/30mm (típico: `1` a `3`).
* `GUNINTVL <segundos>`: Cadência de tiro (intervalo entre tiros, ex: `0.05` para 1200 tiros/min).
* `GUNSIGHT <TRUE|FALSE>`: Habilita retículo de mira preditiva e diretora no HUD.
* `INIT_AAM <qtd>` e `MAX__AAM <qtd>`: Mísseis ar-ar guiados por radar ou infravermelho.
* `INIT_AGM <qtd>` e `MAX__AGM <qtd>`: Mísseis ar-solo / antitanque guiados.
* `INITBOMB <qtd>` e `MAX_BOMB <qtd>`: Bombas convencionais de queda livre ou guiadas.
* `INITRCKT <qtd>` e `MAX_RCKT <qtd>`: Foguetes não guiados em casulos (*pods*).
* `INITFLAR <qtd>`: Cargas de *flares* térmicos de despistamento de mísseis infravermelhos.
* `TRIGGERS <gun> <aam> <agm> <bomb>`: Mapeamento de quais gatilhos acionam cada armamento.

### 6.7 Referências Operacionais para a Inteligência Artificial (Piloto Automático)
* `REFVCRUS <velocidade>`: Velocidade indicada padrão de cruzeiro (ex: `120kt`).
* `REFACRUS <altitude>`: Teto ou altitude ideal de cruzeiro (ex: `8000ft`).
* `REFTCRUS <potência>%`: Regime de potência recomendado em cruzeiro (ex: `70%`).
* `REFVLAND <velocidade>`: Velocidade indicada no toque do pouso (velocidade de aproximação final, ex: `65kt`).
* `REFAOALD <graus>`: Ângulo de ataque ótimo mantido no planeio de pouso (típico: `5` a `8` graus).
* `REFTHRLD <potência>%`: Potência da manete na rampa de aproximação (ex: `35%`).
* `REFLNRWY <comprimento>m`: Comprimento mínimo de pista necessário para pouso seguro.

---

## 7. Manifesto e Registro no Simulador (.lst)

Para que o simulador reconheça a nova aeronave criada, é necessário gerar o manifesto de montagem.

### 7.1 Arquivo Local da Aeronave (`meu_aviao.lst`)
```text
meu_aviao.dat
meu_aviao.dnm
meu_aviao_coll.srf
cockpit.srf
```
* Linha 1: Arquivo `.dat` principal.
* Linha 2: Arquivo `.dnm` visual.
* Linha 3 (opcional): Malha de colisão física (`_coll.srf`).
* Linha 4 (opcional): Malha 3D da cabine interna (`cockpit.srf`).

### 7.2 Registro Global no YSFlight (`aircraft.lst`)
No arquivo central do simulador (geralmente em `YSFLIGHT/aircraft/aircraft.lst`), adiciona-se uma linha com o comando:

```text
meu_aviao meu_aviao/meu_aviao.dat meu_aviao/meu_aviao.dnm
```
* Parâmetro 1: Nome chave identificador único do modelo.
* Parâmetro 2: Caminho relativo do arquivo `.dat`.
* Parâmetro 3: Caminho relativo do arquivo `.dnm`.

---

## 8. Arquitetura Recomendada para a Ferramenta de Criação

Ao desenvolver um editor ou criador de modelos em outro projeto, recomendamos a seguinte arquitetura de componentes e fluxo de dados:

```text
┌────────────────────────────────────────────────────────┐
│             PIPELINE DA FERRAMENTA DE CRIAÇÃO          │
├────────────────────────────────────────────────────────┤
│ 1. Importação 3D (.OBJ, .GLTF, .FBX)                   │
│    └─ Normalização de escala (1 un = 1 metro)          │
│    └─ Conversão Left-Handed (Inverter eixo X)          │
├────────────────────────────────────────────────────────┤
│ 2. Segmentador de Peças (Part Slicer)                  │
│    └─ Fuselagem, Asas, Ailerons, Profundor, Trens      │
│    └─ Isolamento automático de peças móveis            │
├────────────────────────────────────────────────────────┤
│ 3. Calculador de Pivôs (CNT Estimator)                 │
│    └─ Eixo de dobradiça (Bounding Box Center ou Aresta)│
│    └─ Geração automática do vetor CNT                  │
├────────────────────────────────────────────────────────┤
│ 4. Gerador de Simetria (Mirror Tool)                   │
│    └─ Espelha asa esquerda -> asa direita (X = -X)     │
│    └─ Inverte deltas de aileron STA 1 <-> STA 2        │
├────────────────────────────────────────────────────────┤
│ 5. Otimizador de Malha e Cores (.SRF Builder)          │
│    └─ Quantização para paleta 15-bit (opcional)        │
│    └─ Detecção de arestas suaves (Round Shading 'R')   │
├────────────────────────────────────────────────────────┤
│ 6. Montador do Grafo de Cena (.DNM Builder)            │
│    └─ Atribuição de classes CLA 0..31                  │
│    └─ Empacotamento em blocos PCK para arquivo único   │
├────────────────────────────────────────────────────────┤
│ 7. Calibrador Aerodinâmico e Físico (.DAT Editor)      │
│    └─ Cálculo de MTOW e carga alar em tempo real       │
│    └─ Validador de consistência aerodinâmica           │
├────────────────────────────────────────────────────────┤
│ 8. Exportador de Pacote (ZIP / Pasta do YSFlight)      │
│    └─ meu_aviao.dnm, meu_aviao.dat, meu_aviao.lst      │
└────────────────────────────────────────────────────────┘
```

### Algoritmo de Simetrização Automática:
Em uma ferramenta de autoria, modelar ambos os lados da aeronave manualmente gera retrabalho e assimetrias indesejadas. O algoritmo recomendado para espelhar um componente do lado esquerdo para o lado direito é:

```typescript
function mirrorNodeToRightSide(leftNode: DnmNode): DnmNode {
  return {
    ...leftNode,
    uid: `${leftNode.uid}_right`,
    name: leftNode.name.replace(/left|esq|_l/i, 'right'),
    fileName: leftNode.fileName.replace(/left|esq|_l/i, 'right'),
    // 1. Espelha a posição de montagem no eixo X
    pos: {
      ...leftNode.pos,
      pos: { ...leftNode.pos.pos, x: -leftNode.pos.pos.x },
      att: { ...leftNode.pos.att, h: -leftNode.pos.att.h, b: -leftNode.pos.att.b }
    },
    // 2. Espelha o pivô CNT no eixo X
    cnt: {
      ...leftNode.cnt,
      x: -leftNode.cnt.x
    },
    // 3. Inverte as deflexões angulares dos estados STA
    states: leftNode.states.map((st) => ({
      ...st,
      pos: { ...st.pos, x: -st.pos.x },
      att: { ...st.att, h: -st.att.h, b: -st.att.b }
    }))
  };
}
```

---

## 9. Checklist de Validação e Exportação

Qualquer ferramenta de criação deve executar as seguintes validações antes de liberar o modelo para o simulador:

### Checklist Geométrico (.SRF / .DNM):
- [ ] **Orientação de Normais**: Vértices dos polígonos ordenados em sentido anti-horário (evita faces invisíveis por *backface culling*).
- [ ] **Pivô CNT Definido**: Todas as peças com `CLA > 0` possuem coordenadas de pivô `CNT` coincidentes com a linha da dobradiça real.
- [ ] **Ausência de Nós Órfãos**: Todos os nós declaram suas dependências `REL` e os nós pais listam seus filhos via `CLD`.
- [ ] **Malhas PCK com Contagem Correta**: O número de linhas declarado no cabeçalho `PCK <nome> <linhas>` deve ser exatamente igual à quantidade de linhas de texto do bloco `.srf`.
- [ ] **Triângulo de Trem de Pouso Válido**: `LEFTGEAR`, `RIGHGEAR` e `WHELGEAR` devem formar um triângulo de sustentação estável no plano horizontal com $Y$ consistente com o nível do solo da malha 3D.

### Checklist Físico e Aerodinâmico (.DAT):
- [ ] **Consistência de Peso**: $\text{WEIGHCLN} > 0$, $\text{WEIGFUEL} > 0$ e $\text{WEIGLOAD} \ge 0$.
- [ ] **Estol Físico**: $\text{CRITAOAP} > 0^\circ$ e $\text{CRITAOAM} < 0^\circ$ (o ângulo positivo deve ser estritamente maior que o negativo).
- [ ] **Hierarquia de Velocidades**: $\text{MANESPD1} < \text{MANESPD2} < \text{CRITSPED} \le \text{MAXSPEED}$.
- [ ] **Relação Empuxo/Peso**:
  * Caças a jato: $T/W \ge 0.6$ (típico $0.8$ a $1.2$).
  * Aviões a pistão/treinadores: $P/W \ge 120\text{ HP/t}$.
- [ ] **Carga Alar Coerente**: $W/S = \frac{\text{MTOW} \times 1000}{\text{WINGAREA}} \in [40, 750]\text{ kg/m}^2$.
- [ ] **Esfera de Colisão**: $\text{HTRADIUS}$ abrange todo o volume geométrico da aeronave a partir da origem $(0, 0, 0)$.
