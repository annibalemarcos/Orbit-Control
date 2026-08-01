# Orbit Control 2.5.1

Orbit Control é um aplicativo **desktop nativo** para Windows feito em Python e PySide6. Ele controla scripts Python, apps Flask, projetos Node.js, executáveis e comandos locais em uma janela própria — sem navegador, servidor web ou `localhost` para o dashboard.

## O que ele faz

- Adiciona, edita e remove serviços.
- Preenche automaticamente nome, pasta, tipo e ambiente Python ao selecionar um app.
- Reconhece projetos Node.js pela pasta ou pelo `package.json` e lê os scripts disponíveis.
- Detecta `npm`, `pnpm`, Yarn e Bun pelo `packageManager` ou pelo lockfile do projeto.
- Pode instalar dependências Node.js automaticamente antes de iniciar o serviço.
- Oferece um tipo próprio para arquivos `.bat` e `.cmd`, executados pelo `cmd.exe` com logs completos.
- Força UTF-8 nos processos Python, inclusive quando são iniciados por um BAT/CMD, evitando falhas com acentos e emojis nos logs.
- Pode executar `pip install -r requirements.txt` antes de iniciar cada serviço.
- Inicia, para, pausa, retoma e reinicia processos.
- Executa ações em massa nos itens selecionados.
- Reordena os cards por arrastar e soltar e mantém a posição após fechar o aplicativo.
- Alterna entre tema claro e escuro pelo botão de lua/sol e lembra a preferência.
- Mostra PID, CPU, memória, tempo ativo e portas em uso.
- Detecta portas também nos processos-filhos, incluindo o reloader do Flask.
- Exibe logs individuais ao vivo e um log geral.
- Busca por nome, descrição, arquivo, pasta ou argumentos.
- Usa seletores nativos do Windows para arquivos, executáveis e pastas.
- Persiste serviços e estado localmente.
- Oferece autostart e reinício automático por serviço.
- Arquiva o log individual quando um serviço é removido.
- Reorganiza cabeçalho, indicadores, ações em massa e cards conforme a largura da janela.
- Usa uma, duas ou três colunas de serviços sem reservar espaços vazios de layouts anteriores.
- Encurta visualmente nomes e caminhos longos sem perder o valor completo, que continua disponível na dica do mouse.

## Opção 1 — usar imediatamente no Windows

1. Instale o Python 3.10 ou mais recente.
2. Dê dois cliques em `INSTALAR_E_ABRIR.bat`.
3. Nas próximas vezes, use `ABRIR.bat`.

Isso abre uma janela desktop. Nenhum navegador será iniciado.

Para controlar projetos Node.js, instale também o [Node.js](https://nodejs.org/) e o gerenciador usado pelo projeto. npm vem com o Node.js; pnpm e Yarn também podem ser disponibilizados pelo Corepack.

## Opção 2 — gerar `OrbitControl.exe`

1. Instale o Python 3.10 ou mais recente.
2. Dê dois cliques em `GERAR_EXE.bat`.
3. Aguarde a compilação terminar.
4. O executável será criado em `dist\OrbitControl.exe`.

O `.exe` é gerado em modo `one-file` e `windowed`: é um único arquivo e não abre console. A primeira inicialização pode levar alguns segundos porque as bibliotecas da interface são descompactadas temporariamente pelo empacotador.

> O executável do Windows precisa ser gerado no próprio Windows. PyInstaller empacota para o sistema em que está sendo executado; ele não faz compilação cruzada de Linux para Windows.

## Onde os dados ficam

No Windows, configurações e logs ficam em:

```text
%LOCALAPPDATA%\Orbit Control\data
```

Isso mantém seus serviços mesmo quando você substitui o `.exe` por uma versão nova. Use o botão de pasta na barra lateral para abrir esse local.

Os principais arquivos são `services.json` (cadastros e ordem dos cards),
`runtime.json` (estado dos processos), `preferences.json` (tema da interface) e a
pasta `logs`. Cadastros de versões anteriores são migrados automaticamente.

Você também pode definir outro local antes de abrir o app:

```bat
set ORBIT_DATA_DIR=D:\MeusDados\Orbit
OrbitControl.exe
```

## Python usado pelos serviços

Cada aplicativo Python pode ter dependências diferentes. Por isso, o Orbit Control escolhe o interpretador nesta ordem:

1. `python.exe` selecionado manualmente no cadastro do serviço.
2. Caminho definido em `ORBIT_PYTHON`.
3. Ambiente `.venv`, `venv` ou `env` encontrado na pasta do aplicativo (inclusive projetos com a pasta `src`).
4. Python do dashboard, ao rodar pelo código-fonte, ou `py -3`/Python do sistema dentro do `.exe`.

No Windows, a detecção automática prefere `Scripts\python.exe`, preservando `stdout` e `stderr`; o processo continua sem abrir console. O interpretador detectado aparece nas opções avançadas do serviço. Você também pode definir um padrão global antes de abrir o Orbit:

```bat
set ORBIT_PYTHON=C:\Python312\python.exe
OrbitControl.exe
```

Se aparecer `ModuleNotFoundError`, edite o serviço e confira se o interpretador exibido pertence ao projeto correto. Por exemplo:

```text
E:\my_projects\senhas_dashboard\.venv\Scripts\python.exe
```

Ao marcar **Executar pip install -r requirements.txt antes de iniciar**, o Orbit procura esse arquivo na pasta de trabalho, na pasta do script ou um nível acima (útil para `src/app.py`). A instalação usa exatamente o mesmo Python escolhido para o serviço e toda a saída é gravada no log individual. Se o arquivo não existir ou o `pip` falhar, o app não é iniciado e o erro fica explícito no painel.

## Projetos Node.js

Escolha **Projeto Node.js** no cadastro e selecione a pasta que contém o `package.json`. O Orbit preenche o nome e a pasta de trabalho, lê os scripts e detecta o gerenciador nesta ordem:

1. Gerenciador escolhido manualmente no cadastro.
2. Campo `packageManager` do `package.json`.
3. `pnpm-lock.yaml`, `yarn.lock`, `bun.lock`/`bun.lockb` ou `package-lock.json`.
4. npm como padrão.

O campo **Comando / script** aceita tanto nomes curtos quanto comandos completos:

| Entrada no Orbit | Comando executado |
| --- | --- |
| `dev` com npm | `npm run dev` |
| `npm run dev` | `npm run dev` |
| `pnpm dev` ou `dev` com pnpm | `pnpm dev` |
| `yarn start` ou `start` com Yarn | `yarn start` |
| `bun run preview` ou `preview` com Bun | `bun run preview` |

Também são aceitos argumentos e operações personalizadas, como `npm run dev -- --host 0.0.0.0`, `pnpm run preview`, `yarn workspace web dev` ou `bun run server.ts`.

Marque **Instalar/atualizar dependências antes de iniciar** para executar primeiro o comando informado em **Comando de instalação**. O padrão é `install`, mas você pode usar `ci`, `install --frozen-lockfile`, `install --immutable` ou o comando completo. A instalação e o servidor usam o mesmo gerenciador, a mesma pasta, as mesmas variáveis de ambiente e o mesmo log individual.

Se o gerenciador não estiver no `PATH`, informe manualmente `npm.cmd`, `pnpm.cmd`, `yarn.cmd`, `bun.exe` ou até um comando como `corepack pnpm` no campo **Executável (opcional)**. No Windows, arquivos `.cmd` são executados silenciosamente e continuam sob controle do Orbit.

## Tipos suportados

- Python: `.py` e `.pyw`.
- Node.js: pastas de projeto ou `package.json`, com npm, pnpm, Yarn e Bun.
- Arquivos em lote do Windows: `.bat` e `.cmd` (opção **Arquivo BAT / CMD** no cadastro).
- Programas: `.exe`.
- PowerShell: `.ps1`.
- Outros comandos executáveis disponíveis no `PATH`.

Ao selecionar um `.bat` ou `.cmd`, o Orbit preenche o nome com a pasta do arquivo,
define essa pasta como diretório de trabalho e escolhe automaticamente o tipo correto.
Argumentos podem ser informados normalmente e toda a saída do arquivo em lote é enviada
ao log individual, sem abrir uma janela de Prompt de Comando.

### BAT/CMD, UTF-8 e `mode con`

O Orbit define `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8` e `PYTHONUNBUFFERED=1`
para cada serviço. Essas variáveis também chegam a programas Python iniciados de dentro
de um arquivo BAT/CMD. Isso evita erros como `UnicodeEncodeError: 'charmap' codec can't
encode character` ao imprimir acentos ou emojis.

Como os arquivos BAT/CMD são executados silenciosamente, não há uma janela de console
para redimensionar. Remova ou comente linhas como esta no BAT:

```bat
mode con cols=80 lines=30
```

Ela é apenas cosmética e, sem uma janela de console, gera o aviso "A tela não pode ter
o número de linhas e colunas especificado". O aviso não impede o serviço de funcionar.

## Organização dos cards e tema

Use a alça `⠿` no cabeçalho de um card para arrastá-lo até a posição desejada. A nova
ordem é salva imediatamente. Também é possível reorganizar resultados durante uma
busca ou filtro: apenas os cards visíveis trocam de lugar e os demais permanecem em
suas posições.

Durante o arrasto, a atualização visual automática é adiada até o botão do mouse ser
solto. Isso preserva o card usado pelo gesto e evita que a grade desapareça quando uma
atualização de métricas acontece no meio da reorganização.

Na parte inferior da barra lateral, clique na lua para ativar o modo escuro. O ícone
vira um sol; clique nele para voltar ao modo claro. A escolha é salva e restaurada na
próxima abertura do Orbit Control.

O pacote inclui `examples\node-demo`, um pequeno servidor Node.js que pode ser usado para testar o cadastro com o script `dev`.

## Testes

Com o ambiente instalado:

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Observações importantes

- Pausar e retomar dependem da permissão do usuário sobre o processo.
- No Windows, processos gerenciados não abrem janelas de console; a saída vai para o log individual.
- Fechar o Orbit Control não encerra automaticamente os serviços que já estão rodando.
- Reinício automático e autostart são monitorados enquanto o Orbit Control está aberto.
