# Mascote TX 🎄

Mascote de Natal personalizável que anda em cima da barra de tarefas, sobe nas paredes laterais
e reage ao que o Claude Code está fazendo. Usa uniforme com a logo TX, solta poderes e pode ganhar
uma turma de personagens que lutam entre si.

## Instalar

Precisa de Linux com X11 (Ubuntu, Mint, Fedora…), Python 3 com GTK 3. Não precisa de sudo.

```bash
git clone https://github.com/eliseurizzonato/mascote-tx.git
cd mascote-tx
./instalar.sh
```

Sem git: baixe o ZIP em **Code → Download ZIP** no GitHub (ou receba o `mascote-tx.tar.gz`),
extraia e rode `./instalar.sh` dentro da pasta.

O instalador confere as bibliotecas (e diz o comando para instalar as que faltarem), copia o
mascote para `~/.local/share/mascote-tx`, coloca no menu de aplicativos e para abrir junto com o
computador, cria o comando `avatar` no terminal, pergunta se é para ligar ao Claude Code (se
você usa) e abre o mascote. Para atualizar,
rode `git pull` e `./instalar.sh` de novo. Para desinstalar: `~/.local/share/mascote-tx/instalar.sh --remover`.

Não funciona no Windows nem no macOS. No Wayland roda via XWayland e pode não ficar em cima da
barra; nesse caso, entre numa sessão X11 (Xorg).

### Compartilhar

`./empacotar.sh` gera `dist/mascote-tx.tar.gz`, sem prints, configurações nem cache. Mande esse
arquivo para quem quiser.

## Personalizar

Clique direito no mascote → **Personalizar…**. Também dá para abrir com `./mascote.sh personalizar`.
As mudanças aparecem na hora e ficam salvas em `~/.config/mascote-tx/config.json`.

| Opção | Valores |
|---|---|
| Nome | qualquer um (aparece nas falas e no menu) |
| Personagem | Boneco TX (o mascote oficial), Tix (robô), Rena, Gatinho, Pinguim, Boneco de neve, Bolota, Bloquinho e os próprios |
| Chapéu | Gorro de Natal, Boné TX, Chifres de rena, Nenhum |
| Uniforme | Camiseta, Jaqueta, Sem uniforme. A logo pode ser ligada ou desligada |
| Logo | estilos `t›x`, `» setas` e `tiflux`. Cores automáticas (contrastam com o fundo) ou cor da logo e cor da seta escolhidas; a cor da seta também colore os poderes |
| Cores | corpo, uniforme e detalhe |
| Tamanho / velocidade | de 2 a 12 / de 0,3 a 3 (atalhos **Maior** e **Menor** no menu) |
| Estilo sticker, andar nas paredes, falas aleatórias, lutar com a turma | liga e desliga |

### Personagem próprio

Crie um `.json` em `~/.config/mascote-tx/personagens/` (ou em `personagens/` aqui) e reabra o
mascote. O `desenho` é a cabeça: cada linha tem 18 caracteres e a última linha fica logo acima
do uniforme. O tronco, os braços, as pernas, o uniforme, o chapéu e os olhos animados ficam por
conta do mascote.

| Letra | Cor |
|---|---|
| `C` / `c` | corpo / corpo mais escuro |
| `U` / `D` | uniforme / detalhe |
| `B` / `E` | branco / olho |
| outras | definidas em `"cores"` |

Veja o exemplo em [personagens/coruja.json](personagens/coruja.json). Use `"olhos": false`
quando desenhar os próprios olhos.

## Turma e lutas

Clique direito → **Adicionar personagem ➕** cria outro mascote com visual sorteado (personagem,
chapéu e cores). Cada um tem o próprio **Personalizar…** e fica salvo em
`~/.config/mascote-tx/turma/`. **Tirar da turma** apaga o personagem extra; o principal não sai.

- **Lutar com 🥊** (clique direito) escolhe o adversário. Com **Lutas automáticas** ligado, eles
  também se desafiam sozinhos de vez em quando (depois de uma luta, cada um descansa 90 s).
- Na luta eles correm um até o outro, pulam, dão voadoras, combos de socos com chute, rajadas TX
  e explosões de presentes, e recuam. Cada golpe tira vida (barra e número acima da cabeça),
  arremessa rodando, treme e pisca de vermelho; às vezes o golpe é desviado.
- Quem zera a vida cai nocauteado com estrelinhas, e o vencedor comemora. Depois de 45 s sem
  nocaute, dá empate.
- Só o principal reage ao Claude Code; quando o Claude termina, a turma toda comemora junto.

## Luta de stickers 🎮 (você joga)

Clique direito → **Jogar luta 🎮…** (ou `./mascote.sh jogar`). Escolha seu lutador e lute no
teclado contra um bot ou contra um amigo no PC dele. Os lutadores aparecem em cima da barra do
monitor principal com estilo sticker (contorno branco e sombra); a turma some durante o jogo e
volta quando você fecha a janela.

| Tecla | Ação |
|---|---|
| ← → ou A D | andar; com **Shift** segurado ou dois toques rápidos, correr |
| ↑, W ou Espaço | pular (pula por cima da rajada); de novo no ar, pulo duplo; soltar cedo pula mais baixo |
| ↓ ou S | defender (o golpe de frente tira só 1/4) |
| J | soco. Três seguidos fecham com um chute; correndo, vira investida; no ar, voadora |
| K | rajada (recarga 0,9 s) |
| L | especial: explosão de presentes (recarga 5 s) |

### Física maluca, armas e vantagens

- **Física exagerada**: golpe forte arremessa o lutador rodando; ele quica no chão e bate na
  borda da tela e volta. O pulo duplo é uma cambalhota.
- **Armas em presentes 🎁**: de tempos em tempos cai um presente; encoste nele para pegar a arma.
  O bot também vai buscar.

  | Arma | Tecla | Efeito | Usos |
  |---|---|---|---|
  | Bengala | J | golpe com mais alcance, arremessa | 8 |
  | Martelo do Noel | J | lento, dano alto, arremessa longe rodando | 4 |
  | Canhão de neve | K | tiro que congela o adversário por 1 s | 5 |

- **Vantagens (roguelite)**: no fim de cada rodada você escolhe 1 de 3 vantagens, que se somam
  até fechar a janela ou trocar de partida. Contra o bot, ele ganha uma sorteada a cada rodada.

  | Vantagem | Efeito (por nível) |
  |---|---|
  | ❤️ Vida | +20 de vida máxima (até 5×) |
  | ⚡ Velocidade | +15% (até 4×) |
  | 💪 Força | +20% de dano (até 5×) |
  | 🦘 Pulo triplo | mais um pulo no ar |
  | ⏱️ Recarga | golpes e poderes 25% mais rápidos (até 3×) |
  | 🧛 Vampiro | recupera 25% do dano que causa (até 3×) |
  | 🛡️ Casca | leva 15% menos dano (até 3×) |

  No online, os presentes saem no PC de quem hospeda e as armas e vantagens aparecem para os dois.

A luta roda a 60 quadros por segundo, com impacto que congela a tela por um instante, tremida,
faíscas e o dano subindo em número. Quem leva 4 golpes seguidos é arremessado e fica intocável
por um instante, para ninguém ficar preso num combo infinito.

A janela do jogo precisa estar selecionada para o teclado funcionar. O campo **Tamanho** (Mini,
Pequeno, Médio, Grande) muda os lutadores na hora, também no meio da luta, e fica salvo; o
padrão é Pequeno. No online, o lutador do amigo aparece no tamanho que você escolheu.

- **Bot**: fácil, normal ou difícil (ataca mais rápido e desvia mais).
- **Amigo online**: os dois instalam o mascote. Um clica **Hospedar partida** e passa o IP que
  aparece; o outro digita esse IP e clica **Entrar**. Cada um controla o seu lutador e vê a
  mesma luta na própria tela. Usa a porta TCP 47950 (`MASCOTE_JOGO_PORTA` muda).
  - Mesma rede (casa, escritório): funciona direto.
  - Casas diferentes: instalem o [Tailscale](https://tailscale.com) ou o ZeroTier (grátis) e usem
    o IP 100.x que ele dá, ou libere a porta 47950 no roteador de quem hospeda.
  - Se o firewall bloquear: `sudo ufw allow 47950/tcp` em quem hospeda.
- **Revanche** começa outra rodada; o placar conta as vitórias da sessão.
- O painel **📋 Instruções para jogar com um amigo**, na janela do jogo, mostra os comandos de
  instalar e atualizar (com botão **Copiar**) e o passo a passo. **Copiar convite completo** põe
  na área de transferência uma mensagem pronta, com os comandos e o seu IP, para colar no
  WhatsApp ou Slack.

O estilo sticker também pode ser ligado no seu mascote em **Personalizar… → Estilo sticker**.

## Poderes

Duplo clique solta um poder aleatório; o menu **Soltar poder ⚡** escolhe qual. Também saem
sozinhos de vez em quando e às vezes quando o Claude termina.

| Poder | Efeito |
|---|---|
| Rajada TX » | setas `»` voando para a frente |
| Explosão de presentes | estouro de confete e presentes |
| Teletransporte | some e reaparece em outro lugar |
| Superpulo | pulo alto com rastro de faíscas |
| Aura | aura brilhante por 5 s |
| Nevasca | neve forte no monitor |

## O que ele faz

- Anda pela borda da barra. Quando passa para o monitor mais alto, ele pula; na volta, cai.
- Nas bordas da tela, às vezes sobe pela parede lateral e depois desce.
- Sozinho: dá tchau, toma chocolate quente, solta presentes, bengalas e biscoitos e dorme à noite.
- Clique: dá tchau, fala e solta um presente. Arrastar: pega e solta, e ele cai.

| Evento do Claude Code | Reação |
|---|---|
| Nova sessão | Dá tchau |
| Você manda um prompt | Corre pela oficina: "Recebi sua cartinha!" |
| Ferramenta (Bash, Edit, Read…) | Fala o que está fazendo ("Rodando um comando…") |
| Pedido de permissão | Pula e acena até você responder |
| Claude terminou | Comemora, solta um presente e mostra o começo da resposta |
| Subagente | "Um elfo entrou na oficina", solta estrela ou biscoito |

## Comandos

Depois de instalar, digite **`avatar`** em qualquer terminal: abre o mascote (se já estiver
aberto, ele dá tchau). O `avatar` aceita os mesmos comandos do `mascote.sh`: `avatar parar`,
`avatar reiniciar`, `avatar jogar`, `avatar personalizar` etc. Ele é um atalho em
`~/.local/bin/avatar`; se o terminal não achar, abra um terminal novo.

```bash
./mascote.sh iniciar | parar | reiniciar | status | personalizar
python3 instalar_hooks.py            # liga ao Claude Code (faz backup do settings.json)
python3 instalar_hooks.py --remover
./mascote.sh falar "Oi!" presente    # presente, bengala, estrela, biscoito
./mascote.sh nevar
./mascote.sh poder rajada            # rajada, explosao, teleporte, superpulo, aura, nevasca
./mascote.sh config nome '"Rudolfo"'  # muda qualquer opção do principal (o valor é JSON)
./mascote.sh jogar                   # abre a Luta de stickers (bot ou amigo online)
./mascote.sh adicionar rena Rudi     # novo personagem (modelo e nome opcionais)
./mascote.sh lutar Tix Rudi          # luta entre dois (sem nomes: o principal contra um sorteado)
./mascote.sh remover Rudi            # tira um personagem extra da turma
```

API local em `127.0.0.1:47900`:

| Endpoint | O que faz |
|---|---|
| `POST /evento` | recebe os hooks do Claude Code |
| `POST /falar` | `{"texto", "item", "acao", "poder", "mascote"}`; `acao`: `wave`, `cocoa`, `party`, `sleep`, `nevar`, `escalar`, `poder` |
| `GET /config`, `POST /config` | lê e altera a configuração (`"mascote": "nome"` no POST escolhe quem) |
| `POST /adicionar` | `{"modelo", "nome"}`, os dois opcionais |
| `POST /lutar` | `{"a", "b"}`: nomes dos lutadores (opcionais) |
| `POST /remover` | `{"mascote": "nome"}` |
| `POST /jogar` | abre a janela da Luta de stickers |
| `GET /` | status, posição, último evento e a turma (vida e adversário de cada um) |

Variáveis: `MASCOTE_PORTA` (padrão 47900), `MASCOTE_CONFIG` (arquivo de configuração; a turma
fica na pasta `turma/` ao lado dele, útil para testar sem mexer no seu mascote) e `MASCOTE_TIPO`
(`dock`, `utility` ou `notification`, se o gerenciador de janelas esconder o mascote). Log e PID
ficam em `$XDG_RUNTIME_DIR/mascote-tx-<porta>.log` e `.pid`.

Requisitos: X11 com compositor (Cinnamon serve), Python 3 com PyGObject (GTK 3) e pycairo.
