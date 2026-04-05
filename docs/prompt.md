Prompt inicial para novo chat.
Modificado a cada novo chat que é iniciado, de acordo com o progresso de cada sessão de desenvolvimento.

Atualização de código deprecated
Olá!
Nosso projeto é baseado no Flask 3 com Tailwind 4 e Babel.
Usamos firebase com a página inicial estática que espera o CloudRun com nosso container.
Usamos Firestore como banco de dados.
Usamos Google Cloud Secret Manager para armazenar dados sensíveis.
Temos uma documentação do desenvolvimento no diretório docs, sendo o journal.md o mais relevante.
Estamos desenvolvendo cada módulo como blueprints do Flask.
Temos o módulo rag_agent, g_calendar_agent e o whatsapp funcionando. Hoje só rag_agent interage com WhatsApp.
Durante desenvolvimento e migrações houve um descuido em relação aos módulos sugeridos e acabei concordando com a adoção de código, que estou revisando e constatando que ou já estão "deprecated", ou em vias de sê-lo.
Nosso missão nessa sessão é buscar e trocar essas partes de código, substituindo por versões mais atuais.
Como sua referência é sempre desatualizada, temos, obrigatóriamente, que fazer uso de documentão atualizada da LangChain disponível via MCP server que instalamos: "https://docs.langchain.com/mcp".
Vamos começar pelo rag_agent.
Vamos repassando o código aos poucos e resolvendo os conflitos gradativamente.
Veja se tem alguma pergunta adicional.
Caso não tenha dúvidas, pode gerar seu plano.