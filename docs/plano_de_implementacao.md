# Plano de Implementação: edcat_v2

Este documento visa documentar as fases e a arquitetura oficial da versão 2 do projeto, abstraída das lições aprendidas e documentadas no projeto original (V1).

A abordagem baseia-se em passos técnicos objetivos, garantindo reprodução, resiliência e foco nas melhores práticas.

## Pilares Arquiteturais (Lições Apreendidas do V1)
- **Autenticação Stateless**: Utilizar exclusivamente o cookie `__session` (com tags `Secure=True` e `SameSite='None'`) para evitar bloqueios do cache agressivo do Firebase Hosting e restrições do Web Preview (iframe).
- **Escopo do Cloud Run**: Injeção imperativa das variáveis de ambiente (como `GOOGLE_CLOUD_PROJECT`) em produção para que o contêiner não fique cego. Todo deploy deve apontar para o `digest` (sha256) e usar arquivos `service.yaml`.
- **Roteamento Firebase Hosting**: Configuração do `firebase.json` apontando `"public": "public"` (uma pasta intencionalmente vazia) e efetuando "rewrites" absolutos para o Cloud Run. Isso extingue o erro `Site Not Found`.
- **Gerenciamento de Dependências**: Utilizar o `uv pip compile` focado no arquivo `requirements.in` para garantir as últimas versões das sub-dependências com um grafo limpo.
- **WBA (WhatsApp) pausado**: Visto que o registro de API de Negócios exige CNPJ (Business Verification), a integração WBA fica em espera. O foco do módulo inteligente será o desenvolvimento desacoplado do agente RAG (IA).

---

## Fases do Projeto

### Fase 1: Fundação, Estrutura Core e i18n
O foco inicial é preparar o terreno, garantindo que as fundações estejam corretas sob o pacote de gestão `uv`.

- [ ] Instanciar o `pyproject.toml` (ou `requirements.in`) para suportar o ambiente.
- [ ] Incorporar: Flask, Gunicorn, `firebase-admin`, `google-cloud-secret-manager`, `flask-babel`, e utilitários dotenv.
- [ ] Recriar a estrutura `Application Factory` (`edcat_root` -> `create_app`).
- [ ] Definir o `Flask-Babel` gerenciando traduções com o roteamento unificado `/<lang_code>`.
- [ ] Configurar o **Tailwind CSS v4** de forma modular, permitindo a compilação paralela contínua no `static`.

### Fase 2: Segurança, Dados e Cookies
Garantir o fluxo de sessão customizado e conexão de banco de dados por meio do Secret Manager.

- [ ] Implementar as rotinas de busca de segredos (`ADMIN_USERS`, `TESTER_USERS`, `firebase-credentials`) utilizando as abordagens corrigidas (ex: `.strip()` para evitar quebras de linha (`%0A`)).
- [ ] Inicializar o Firebase App e Firestore atrelados ao Secret Manager.
- [ ] Recriar os decorators assíncronos de `@login_required`, `@load_user_profile`, resgatando o sistema de controle de acesso (Roles/Papéis).

### Fase 3: UI, Painéis e Interface
Aproveitando o setup do Tailwind CSS, criaremos designs focados na alta qualidade visual.

- [ ] Renderizar templates vitais: Login, Dashboard Administrativo, Tela Pública.
- [ ] Trazer as rotas base (`views.py`) conectadas a estes templates.

### Fase 4: Integração de I.A. (RAG Agent) Independente
Com o WBA em pausa para burocracias do WhatsApp Bureau, focaremos em um sistema de testes paralelo.

- [ ] Criar o Blueprint web-temporário (`/rag-test`).
- [ ] Construir a lógica do agente autônomo.

### Fase 5: Dockerização Baseada em Sha256 e CI/CD
Procedimentos rigorosos para evitar o "Deploy Fantasma".

- [ ] Definir um Dockerfile enxuto de estágio duplo (Multi-stage build) rodando Gunicorn + ProxyFix.
- [ ] Setup do `service.yaml` com todas as variáveis obrigatórias documentadas.
- [ ] Scripts de automação `devserver.sh` consolidados para o desenvolvedor local se orientar.

# 📅 Plano Final: Agente de Agendamento - Consultório Dental (MVP)

Este plano detalha a implementação final do agente de agendamento, focado na coleta de dados do cliente e no cumprimento fiel da grade de horários do consultório.

## 1. Regras de Negócio Inegociáveis

> [!IMPORTANT]
> **Grade de Horários Semanal**:
> - **Segunda, Terça, Quinta, Sexta**: 08h-11h (Manhã) e 14h-17h (Tarde).
> - **Quarta**: **FECHADO** (Não mostrar na tabela).
> - **Sábado**: 08h-11h (**Apenas Manhã**).
> - **Domingo**: **FECHADO**.

> [!IMPORTANT]
> **Bloqueios de Data (Blackout)**:
> - O sistema permitirá uma lista de datas específicas (ex: `2026-04-17`) que serão removidas da disponibilidade, independente do dia da semana.

> [!IMPORTANT]
> **Fluxo Conversacional**:
> 1. Perguntar o **Nome**.
> 2. Perguntar o **Telefone**.
> 3. Perguntar o **Motivo** (ex: "estou com dor de dente").
> 4. Apresentar Tabela de Disponibilidade (UX `3h - tarde`).
> 5. Confirmar e Criar Evento.

## 2. Implementação Técnica

### A. Serviços (`services.py`)
- **Configuração de Agenda**: 
    - Objeto `WORKING_HOURS` mapeando dias da semana (0-6).
    - Lista `EXCLUDED_DATES` para bloqueios manuais.
- **Formatação de Título**: 
    - O evento no Google Calendar será criado como: `{NOME} - {TELEFONE} - {MOTIVO}`.

### B. Agente e Ferramentas (`agent.py` & `tools.py`)
- **System Prompt**: Definir o "tom de voz" de um recepcionista profissional. Instruir para coletar as 3 informações antes de sugerir horários.
- **Ferramentas**:
    - `get_available_slots_tool`: Retorna a tabela Markdown dos próximos 6 dias úteis seguindo a grade.
    - `confirm_booking_tool(name, phone, reason, slot_iso)`: Faz a inserção final.

### C. Observabilidade
- Tracing completo no **LangSmith** para validar se o agente está coletando os dados corretamente e convertendo os horários amigáveis para ISO.

## 3. Questões Resolvidas
- **Cancelamento**: Não implementado nesta fase (MVP).
- **Cadastro**: Será feito via perguntas diretas pelo agente de calendário (futuramente integrado a um banco de dados).

## 4. Plano de Verificação
- **Teste de Grade**: Verificar se Quarta-feira e Domingo sumiram da tabela.
- **Teste de Sábado**: Verificar se no Sábado apenas as opções de "manhã" aparecem.
- **Teste de Criação**: Validar se o título do evento no Calendar contém todas as informações coletadas.
