# Diário de Bordo da Migração: EdCat V1 ➡️ V2
*Um registro das decisões arquitetônicas e da evolução técnica do sistema.*

---

## 1. O Ponto de Partida e o Paradigma "V2"
A plataforma original (V1) representava o esforço inicial hospedado estaticamente/client-side no Firebase Studio. Apesar de funcional, arquiteturas baseadas excessivamente em requisições de frontend puro costumam enfrentar barreiras de Caching (especialmente via Firebase Hosting + CDN) e problemas na segurança de regras de acesso com o passar do tempo.

Migrar para o projeto **EdCat V2** significou a adoção nativa do paradigma **S.S.R.** (Server-Side Rendering) suportado por containers de alta performance. 

## 2. Stack Tecnológica e Ferramental Adotado
O setup foi reimaginado do zero para máxima performance e modularidade:
* **Gerenciamento Extremamente Veloz**: Em vez de `pip` tradicional ou `poetry`, adotamos o **`uv`** (escrito em Rust), que monta os `.venv` e processa de forma praticamente instantânea.
* **Flask Application Factory**: Abandono de scripts lineares para abraçar o pattern `create_app()`. Isso permitiu um isolamento fenomenal dos recursos (Banco de Dados, Autenticação, Rotas).
* **Babel Preservado (i18n)**: Restauramos a capacidade multilíngue de todo o legado usando o sistema de catálogos padrão (`messages.po`). O site está traduzível instantaneamente mudando a URL de `/pt_BR/` para `/en_US/`.

## 3. A Grande Mudança: Autenticação Stateless e Secret Manager
Este foi um dos maiores saltos do projeto:
* **Firebase Auth Via Cookie Mágico (`__session`)**: Ao invés de trafegar o `idToken` a cada request ou salvá-lo de forma vulnerável no `localStorage`, nós acoplamos o framework Flask para negociar um **Session Cookie do Firebase**. *Detalhe de Gênio:* Nomear o cookie cirurgicamente como `__session` para violar proativamente a parede de cache de CDNs no ambiente Google Cloud.
* **GCP Secret Manager Nativo**: Acabamos com as credenciais em plain-text no código fonte. Todos os acessos vitais (`website-secrets`, Service Accounts, Firebase Configs) são puxados criptografados on-the-fly pelo Google `SecretManagerServiceClient`. O código na máquina e no repositório agora são limpos, blindados e imutáveis.

## 4. Interface, UX e Modernização Front-end
Para atender ao requerimento "Nós somos visuais", todo a apresentação original foi atualizada mas semanticamente preservada:
* **Tailwind V4 + Flowbite**: Implementação da nova era de estilização atômica (`tailwindcss/cli`) operando stand-alone (sem os pesos de um diretório massivo `node_modules`).
* Componentes de alto nível do Flowbite aplicados de forma cirúrgica (Navbars Responsivas, Dropdowns Inteligentes de Idioma, Glassmorphism Cards) abrindo caminho de rodízio para um Full-Dark Mode no futuro.

## 5. O Ganho Oculto: Inteligência MCP (Model Context Protocol) 🧠
Durante a migração de Antigravity, o grande catalisador de produtividade foi a utilização dos \*\*Servidores MCP\*\*:
* A IA de apoio deixou de "alucinar" lógicas antigas da documentação e passou a consumir **diretamente a documentação oficial real-time** via servidor MCP do Tailwind/Flowbite e do Firebase.
* Insights ultra-precisos evitaram horas de debugging. Mudanças de bibliotecas v8 para v9 do Firebase ou atualizações do Tailwind V3 para V4 foram absorvidas pelo motor IA sem falhas e convertidas em código de produção em poucos minutos.

## 6. Gotchas de Vida Real: O Conflito Jinja vs Prettier (IDE Formatters)
Durante a formatação do HTML (*UX Polish*), descobrimos e vencemos dois erros técnicos sutis que engolem horas de desenvolvedores no Jinja:
* **Falso Comentário HTML:** O motor do Jinja projeta variáveis servidor ANTES da tela. O HTML não esconde lógica de template. Proteger os desenvolvedores comentando `<!-- Atenção: {{ _() }} -->` resulta em um **Crash Fatal (Error 500)**. O Jinja tenta ler a função de linguagem mas não encontra texto dentro. A lição: Comentários que bloqueiam script têm que ser da família do Flask/Jinja `{# ... #}`.
* **Formatadores Automáticos vs Dicionários Babel:** A grande descoberta visual: dar um `Alt+Z` ou salvar um `index.html` (Prettier ativado) reorganiza blocos e quebra os componentes longos para as margens ideais. Isso injeta espaçamentos invisíveis (`\n`) no meio da tag `{{ _('Texto') }}`. Isso rompe silenciosamente as traduções Português, isolando o `.po`, pois o Babel procura apenas palavras em fila exata.
  * **Solução:** Não, não é necessário colar marcações loucas por todo o site. Basta inserir um `<!-- prettier-ignore -->` solitário logo acima dapenas de **parágrafos imensos de texto Babel**. Palavras simples tipo "_('Login')" não precisam de nada, o Prettier nunca vai quebrá-las.

## 7. O Renascimento da Inteligência (LangChain RAG) e a Resiliência do Sistema
A transição da inteligência conversacional exigiu muito mais do que copiar arquivos, focamos na "Morte Limpa" (Fail-Safe) da API:
* **Vanguarda LangChain 0.3+**: O código legado de `create_react_agent` (depreciado) foi reescrito pela fundação estável atualizada (`create_agent`). Incorporamos a força revolucionária do `gpt-5-mini` extraindo contextos da coleção local `ChromaDB` embarcada (base `Jung_Individuacao`).
* **Blindagem de Falhas (Safe Mode)**: Garantimos que o Flask seja imortal. Se a cotação do limite da OpenAI esgotar ou o servidor Chroma faltar arquivos, o aplicativo NÃO crasha na inicialização nem derruba o site do aluno. O agente se reporta offline, mas a navegação do sistema web continua flutuando a 100%.

## 8. Webhooks do WhatsApp Acoplados 
O motor de comunicação da Meta/WhatsApp (Graph API V24) foi resgatado e lapidado em níveis críticos de segurança:
* **Caching de Secretos Anti-Gargalo**: O `services.py` agora não liga para a cloud para buscar chaves do WhatsApp a cada requisição enviada. Ele acessa uma memória Dictionary leve após a primeira consulta, polpando os servidores da Google e agilizando as respostas do Chatbot no Whatsapp.
* **Corrigindo as Rotas Silenciosas**: A adequação da URL para honrar o Painel Desenvolvedor da Meta exigiu um roteamento cirúrgico em Blueprint global (`url_prefix='/whatsapp'`) em união estrita com o Invoker do Agente RAG.

## 10. Manutenção e Fluxo de Trabalho (Workflow)
Para garantir que a V2 continue evoluindo sem fricção em novos ciclos de desenvolvimento:
* **Persistência de IA (ChromaDB)**: A base de conhecimento reside em `edcat_root/resources/chroma_db`. Estrategicamente, ela é ignorada pelo Git (para evitar binários pesados no histórico) mas incluída no `.gcloudignore`, garantindo que cada Deploy leve consigo a versão mais atualizada do conhecimento da IA embutida na imagem Docker.
* **Comandos de Sobrevivência Local**:
  - `uv run main.py`: Inicia o servidor Flask com hot-reload.
  - `.\run_npx.bat`: Mantém o compilador Tailwind V4 vigiando mudanças no CSS/HTML.
* **Gestão por Artefatos**: O sucesso desta migração deve-se ao uso estrito de *Planos de Implementação* e *Walkthroughs* documentados em tempo real, permitindo que a inteligência artificial de apoio (Antigravity) mantenha o contexto perfeito mesmo após resets de sessão.

## 11. Resiliência de Webhook: O Problema do Timeout da Meta
Durante a fase final, resolvemos um "bug" sistêmico crítico causado pela latência da IA:
* **Gatilho**: A Meta interrompe a conexão HTTP caso uma resposta do webhook demore mais de 15 segundos. Como o Agente RAG/OpenAI pode levar ~18s, a Meta interpretava como falha e disparava **retries automáticos** infinitos.
* **Sintoma**: O bot respondia várias vezes à mesma pergunta do usuário.
* **Solução (Deduplicação)**: Implementamos um filtro de mensagens no `routes.py` usando um `deque` (LRU cache) para rastrear `message_id`s processados. Se um ID repetido chega em menos de 15s (retry), o sistema devolve imediatamente um HTTP 200 "OK" sem evocar a IA de novo, quebrando o loop de spam.

## 12. A Saga do Agente de Agendamento (Google Calendar)
A implementação do `g_calendar_agent` foi um dos maiores desafios de integração da V2, servindo como laboratório para a transição definitiva para o modelo "Zero-Disk":

*   **O Desvio do ADK**: Inicialmente, tentamos adotar o *Agent Development Kit (ADK)* para padronização. Contudo, a complexidade de acoplamento e a dependência de estruturas locais provaram-se um gargalo para a agilidade necessária. Decidimos abortar o ADK em favor de uma implementação customizada e leve, focada em ferramentas (`tools`) puras.
*   **Do Legado à Vanguarda (LangChain 0.3+)**: O código inicial sofria com a latência de chamadas diretas e padrões depreciados (`create_react_agent`). Ao refatorarmos para `create_agent` e `init_chat_model`, a performance saltou: o tempo de resposta caiu de ~70 segundos para impressionantes **9 segundos**.
*   **A Batalha do Cloud Run (Statelessness)**: O maior obstáculo foi a volatilidade do sistema de arquivos do Cloud Run. Migramos o sistema de autenticação do Google (OAuth 2.0) de arquivos `token.json` locais para strings JSON persistidas no **Secret Manager**. 
*   **O Loop dos Segredos**: Aprendemos uma lição valiosa sobre o ciclo de vida de containers. Como o Agente é um *Singleton* (inicializado no boot do Flask), a adição de segredos como a `GOOGLE_API_KEY` exigiu um redeploy forçado para que o container "limpasse" o estado de erro da memória e reconhecesse a nova configuração da nuvem.


## 13. Refatoração LangChain v1.0 e Padronização de Utilitários
Em Abril de 2026, iniciamos uma fase de "Polimento de Vanguarda" para alinhar o código com os padrões definitivos do LangChain v1.0 e organizar a arquitetura de arquivos para suportar escala:

*   **Migração para o Namespace Simplificado**: Seguindo as diretrizes de 2026, abandonamos classes de integração direta (como `OpenAIEmbeddings`) em favor das funções de fábrica unificadas `init_embeddings` e `init_chat_model(..., output_version="v1")`. Isso torna os agentes agnósticos a provedores e prontos para o novo padrão de blocos de conteúdo.
*   **Isolamento de Tracing via Contexto**: Substituímos o uso de `LangChainTracer` (deprecated) pelo `langsmith.tracing_context(project_name="...")`. Isso resolveu conflitos em ambientes multithreaded no Cloud Run, garantindo que o agent RAG e o Calendar tenham isolamento total de logs sem depender de variáveis de sistema globais.
*   **Nascimento do Pacote `utils`**: Para profissionalizar o projeto, removemos arquivos soltos na raiz. Criamos o pacote `edcat_root/utils/` contendo:
    *   `get_google_secrets.py`: A única fonte da verdade para o Secret Manager, eliminando 4 definições duplicadas da função `get_secret` espalhadas pelos agentes.
    *   `helpers.py`: Centralizador de lógica de parsing resiliente, incluindo o tratamento defensivo de datas ISO para o `gemini-2.5-flash-lite`.
*   **Otimização de Build (Docker)**: Realizamos uma auditoria no `Dockerfile`, removendo `COPY` redundantes e implementando um `.dockerignore` rigoroso. Isso reduziu o tamanho da imagem final e acelerou o ciclo de CI/CD ao evitar o upload de lixo local (`.venv`, `node_modules`).

---
*Status Atual*: Refatoração v2.2 Concluída. Arquitetura Modular, Stateless e "DRY" (Don't Repeat Yourself).
