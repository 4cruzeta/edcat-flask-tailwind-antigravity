# Diário de Bordo: Estabilização do Agente de Calendário e Preparação de Container (Julho 2026)

Este capítulo documenta as soluções aplicadas aos desafios de concorrência, polling, persistência de estado (LangGraph) e configurações de ambiente enfrentados durante a estabilização do blueprint `g_calendar_agent` no projeto **EdCat V2**.

---

## 1. O Problema do Polling Infinito e Desconexão de Estados

### Diagnóstico
Na arquitetura herdada, o frontend do chat fazia uma requisição `POST /ask` que enfileirava a tarefa e retornava imediatamente, enquanto um endpoint `/poll/<session_id>` realizava requisições repetidas a cada 2 segundos esperando a resposta.
Identificamos dois problemas centrais:
1. **Instâncias Separadas de Memória**: O processador local da fila (`_simulate_local_task`) criava uma instância temporária de `CalendarAgent`, enquanto a rota `/poll` buscava o estado a partir de uma instância singleton em `worker.py`. Como o `MemorySaver` guarda os checkpoints em RAM, o histórico da conversa do `/ask` nunca era visto pelo `/poll`, resultando em um loop de carregamento infinito ("3 dots floating") na tela.
2. **Latência Inaceitável**: A tentativa anterior de mitigar isso usando Firestore como checkpointer de nós causava latências severas de rede a cada passo do grafo.

### Solução
* **Fluxo Síncrono no Web Client**: Simplificamos a arquitetura local. A rota `/ask` agora invoca o agente diretamente e aguarda o término do processamento, devolvendo a resposta final na mesma transação HTTP.
* **Remoção de Polling**: O endpoint de polling e a lógica de loop no frontend [calendar_agent.html](file:///E:/1-workspace/Google/Antigravity/edcat_v2/edcat_root/g_calendar_agent/templates/calendar_agent.html) foram completamente removidos.
* **Preservação de Contexto (RAM)**: O executor local passou a utilizar o singleton `get_agent()` de `worker.py`, mantendo a persistência multi-turno do `MemorySaver` ativa e correta entre requisições subsequentes.

---

## 2. A Guerra das Chaves de API (Warning do SDK `google-genai`)

### Diagnóstico
Ao inicializar o cliente do Gemini, o console exibia o aviso persistente:
`WARNING:google_genai._api_client:Both GOOGLE_API_KEY and GEMINI_API_KEY are set. Using GOOGLE_API_KEY.`

Isso ocorria porque a variável `GOOGLE_API_KEY` estava gravada no arquivo local `.env` (carregado no boot do Flask via `load_dotenv()`), enquanto o bootstrap buscava a chave correta no Secret Manager e a definia como `GEMINI_API_KEY`. Como o SDK do Google GenAI é importado na inicialização dos blueprints, ele lia e cacheava ambas do processo.

### Solução
* **Limpeza de `.env`**: Alteramos a chave local no arquivo [.env](file:///E:/1-workspace/Google/Antigravity/edcat_v2/.env) de `GOOGLE_API_KEY` para `GEMINI_API_KEY`.
* **Sanitização Pró-Ativa no Boot**: Injetamos uma rotina no início da função `create_app()` em [__init__.py](file:///E:/1-workspace/Google/Antigravity/edcat_v2/edcat_root/__init__.py):
  ```python
  google_key = os.environ.get("GOOGLE_API_KEY")
  if google_key:
      os.environ["GEMINI_API_KEY"] = google_key
      os.environ.pop("GOOGLE_API_KEY", None)
  ```
  Isso remove a `GOOGLE_API_KEY` do dicionário de ambiente do processo antes que qualquer biblioteca do Google seja importada, sanando de vez o aviso.

---

## 3. Preparação do Container Docker (Cloud Run)

### Diagnóstico
Ao analisar o pipeline de empacotamento, detectamos duas falhas potenciais que impediriam o correto funcionamento da aplicação em produção:
1. **Amnésia do Agente RAG**: A pasta de vetores do ChromaDB (`edcat_root/resources/chroma_db`) estava listada no [.dockerignore](file:///E:/1-workspace/Google/Antigravity/edcat_v2/.dockerignore). Se buildado assim, o container subiria sem a base de conhecimento do chatbot, deixando o RAG offline.
2. **Segurança de Lockfile**: Modificações recentes nas dependências do projeto poderiam causar falhas de sincronização no comando `uv sync --frozen --no-dev` executado no container.

### Solução
* **Retirada de Exclusão**: Comentei a linha do `chroma_db` no [.dockerignore](file:///E:/1-workspace/Google/Antigravity/edcat_v2/.dockerignore), assegurando que a base de conhecimento de Jung/Arquétipos seja copiada e embutida na imagem final do container.
* **Garantia de Build Sincronizado**: Executei o `uv lock` para validar e fixar a árvore completa de dependências no `uv.lock`.

---

## 4. Lições Aprendidas para o Futuro

1. **A simplicidade vence a complexidade desnecessária**: Em ambientes locais de desenvolvimento e homologação de agentes autônomos, fluxos síncronos são muito mais fáceis de depurar e depuram erros de estado em RAM instantaneamente.
2. **Cuidado com cache de importações do Python**: Variáveis de ambiente que configuram SDKs (como chaves de API) devem ser limpas ou definidas no ponto de entrada absoluto do código (`create_app()`), antes de qualquer blueprint ou modelo ser importado.
3. **Persistência Volátil vs Persistência de Auditoria**: Usar persistência local em RAM (`MemorySaver`) resolve problemas de concorrência e latência no fluxo conversacional ativo. Dados de auditoria e confirmações de reserva finais devem continuar sendo gravados em banco persistente (Firestore) de forma assíncrona ou em nós finais de confirmação, nunca no caminho crítico de cada iteração da conversa.
