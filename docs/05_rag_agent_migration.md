# Migração e Reestruturação do Agente RAG V2 (Langchain)

Este documento registra a estratégia adotada para refatorar o sistema de Inteligência Artificial Conversacional (LangChain + ChromaDB) presente no antigo projeto (V1) para o novo paradigma do Flask Application Factory (V2).

## Problemas Técnicos da V1 Superados

A arquitetura originária possuía pontos críticos de falha:
1. **Ponto de Quebra Fatal (Hard Crash):** O arquivo `rag_agent.py` era intrínseco e disparava falhas abruptas durante o `create_app()` caso a chave `OPENAI_API_KEY` falhasse. Isso significava que um Timeout da OpenAI offline derrubaria todo o Application Web Edcat (ninguém conseguiria logar).
2. **Sistema Arquitetural Espalhado (Spaghetti):**
   - Havia um Blueprint `/api/routes.py` só para intermediar post de JSON.
   - Havia um `/web_client/` só para hospedar um index HTML da sala de bate-papo.
   - O banco estático e vetorizado (`chroma_db`) estava isolado da raiz do servidor.

## Nova Solução Construída na V2

### 1. Inicialização Preguiçosa e Resiliente (Soft Fail)
O instanciador do Langchain no V2 agora conta com um encapsulamento de segurança. Se o LangChain falhar ao subir no `__init__.py`, o aplicativo Flask silencia o erro, permite que milhares de estudantes/usuários loguem no site principal, e o erro se revela *apenas* se o usuário tentar abrir especificamente a aba de "Conversar com o Agente Chat".

### 2. Contêinerização Estratégica
A pasta `resources/chroma_db/` pesada foi transferida fisicamente para **dentro** do pacote python (`edcat_root/resources/chroma_db`).
O *Racional:* Durante a "Build" no Google Cloud Run, o Cloud Build compacta a pasta do app como imagem imutável. Arquivos do lado de fora do escopo seriam perdidos, gerando "amnésia" fatal no bot.

### 3. Blueprint Modular "Encapsulado"
Agora o código do Agente, as requisições Web-fetch e as rotas da Chat Engine moram de forma elegante na pasta auto-suficiente:
- `edcat_root/rag_agent/agent.py` (Lógica LLM).
- `edcat_root/rag_agent/routes.py` (Blueprint de API).
- `edcat_root/pages/templates/chat_agent.html` (Renderização de Interface Integrada ao Tailwind CSS V4).

### 4. Gerenciador Inteligente
Migramos dependências via `uv`. Subimos os pacotes da Langchain e do Banco Vetorial e os lockamos nativamente para deploy seguro e rápido na GCR.
