Prompt inicial:
Nosso projeto é baseado no Flask 3 com Tailwind 4 e Babel. 
Usamos firebase com a página inicial estática que espera o CloudRun com nosso container. 
Usamos Firebase como banco de dados. 
Usamos Google Cloud Secret Manager para armazenar dados sensíveis. 
Temos uma documentação do desenvolvimento no diretório docs, sendo o journal.md o mais relevante. 
Estamos desenvolvendo cada módulo como blueprints do Flask. 
Temos o módulo rag_agent e o WhatsApp que interagem de forma que é possível consultar o Chroma DB através do WhatsApp. 
Nosso próximo blueprint será do Google Calendar, um agente que lida com o aplicativo. 
Já temos um código funcional como exemplo que vamos melhorar. 
Se quiser analisar o código para tomar como base, ele é baseado no Google ADK e está no diretório "E:\1-workspace\Google\agents\ADK\workspace\my_calendar"
Tenho algumas dúvidas quanto às funções do código e quanto a qualidade dos prompts que quero esclarecer com você em primeiro lugar. 
Antes de começar a codificar, vamos discutir o projeto, ok?

---

# 📅 EdCat V2 - Fase 3: Google Calendar Agent (Finalizado)
*Expandindo a inteligência da EdCat para ações do mundo real.*

## 🎯 Status da Fase
A implementação do Agente de Calendário foi consolidada com sucesso utilizando a stack **LangChain + LangGraph**. Esta arquitetura substituiu a tentativa inicial com o Google ADK, que apresentou instabilidades severas de concorrência com o ambiente Flask/Windows.

---

## 🛠️ Arquitetura Final da Solução

### 1. Motor de IA: LangChain & LangGraph
- **Modelo:** `Gemini 2.5 Flash` (via `langchain-google-genai`).
- **Orquestração:** O agente é um **StateGraph** (LangGraph). Isso permite que o sistema gerencie o ciclo de "Pensamento -> Ação (Ferramenta) -> Observação -> Resposta" de forma controlada e sem loops infinitos.
- **Observabilidade:** Integração nativa com o **LangSmith** para monitoramento de tracing, latência e custo em tempo real.

### 2. Camada de Ferramentas (Tools)
- As ferramentas foram construídas com **Pydantic Schemas** rigorosos para garantir que o Gemini envie argumentos precisos.
- **Serviços:** `create_event`, `search_events`, `list_events`, `delete_event`.
- **Parsing:** Uso de `dateparser` e `pytz` para garantir que o Agente entenda "hoje", "amanhã às 15h" e converta corretamente para o fuso horário `America/Sao_Paulo` (UTC-3).

### 3. Autenticação OAuth 2.0 (Google Cloud)
- **Modo:** Utiliza o fluxo de `InstalledAppFlow` (via `google-auth-oauthlib`).
- **Arquivos:** `credentials.json` (fornecido pelo desenvolvedor) e `token.json` (gerado automaticamente no primeiro acesso).
- **Escopos:** Acesso total à API do Google Calendar v3.

### 4. Interface Web (EdCat Blueprint)
- Foi criado um blueprint dedicado no Flask: `g_calendar_agent`.
- **Rota de Teste:** `/pt_BR/calendar/test` (GUI de chat moderna com Tailwind 4).
- **Endpoint API:** `/pt_BR/calendar/ask` (Endpoint síncrono que aciona a execução do grafo).

---

## ✅ Lições Aprendidas e Ajustes Críticos

- **Flask vs Async:** O LangGraph provou ser muito mais estável que o ADK para rodar dentro de rotas Flask no Windows, pois não tenta "sequestrar" o loop global de eventos.
- **Parsing de Mensagem Gemini:** O Gemini pode retornar o conteúdo da mensagem como uma lista de partes (mesclando texto e chamadas de ferramenta). Implementamos um filtro no backend para extrair apenas o texto final e evitar o erro `[object Object]` no frontend.
- **Static Discovery:** Em todos os builds de serviço, o parâmetro `static_discovery=False` foi ativado para evitar logs de aviso e potenciais loops de reinicialização do Flask causados por cache de descoberta.

---

## 🚀 Próximos Passos
1. **Integração WhatsApp:** Acoplar o `calendar_graph_agent` ao blueprint do WhatsApp para permitir agendamentos via conversação direta no celular.
2. **Cloud Run Security:** Migrar o `credentials.json` e o `token.json` para o **Google Secret Manager** para garantir que o container seja 100% *stateless* em produção.

*Documentação atualizada em: 03/04/2026*
