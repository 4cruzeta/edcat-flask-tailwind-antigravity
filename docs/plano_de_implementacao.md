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

# 📅 Plano Final: Agente de Agendamento - Consultório Dental (Vanguarda 2026)

Este plano detalha a implementação do agente especialista de agendamento, redesenhado para atuar como um "trabalhador especializado" que será futuramente orquestrado por um Agente Supervisor.

## 1. Regras de Negócio e Especialização

> [!IMPORTANT]
> **Estratégia Proativa**: Ao ser invocado pelo Supervisor (ou ao iniciar o fluxo de agendamento), o agente não deve esperar o cliente perguntar. Ele deve **proativamente** buscar a grade dos próximos 6 dias úteis e apresentá-la.

> [!IMPORTANT]
> **Grade de Horários (Fixo via Código)**:
> - **Seg, Ter, Qui, Sex**: 08h-11h e 14h-17h.
> - **Quarta**: FECHADO.
> - **Sábado**: 08h-11h (Manhã apenas).
> - **Domingo**: FECHADO.

## 2. Fluxo Conversacional "Hands-On"

1.  **Início Imediato**: O agente chama `get_available_booking_slots_tool(days_ahead=6)`.
2.  **Apresentação UX**: Exibe a tabela Markdown e solicita: "Qual destes horários fica melhor para você?".
3.  **Coleta de Dados**: Se as informações (Nome, Telefone, Motivo) não vierem no contexto inicial do Supervisor, o agente as solicita de forma cordial.
4.  **Confirmação**: Após a escolha do horário, o agente usa a `confirm_booking_tool`.

## 3. Implementação Técnica (Refinamento)

### A. Ferramentas (`tools.py`)
- **Remoção de Ambiguidade**: A descrição das ferramentas deve enfatizar que o sistema opera em **Dias Úteis**. Se o usuário pedir "amanhã" e for sábado, o agente deve explicar que a clínica não abre (ou abre só de manhã) se for o caso, baseando-se no retorno da ferramenta.
- **Pydantic**: O campo `days_ahead` será mantido para flexibilidade, mas o `system_prompt` forçará o uso de `6` como padrão de excelência.

### B. Prompt do Agente (`agent.py`)
- **Novo Role**: "Você é o Especialista de Agendamento. Seu único objetivo é levar o cliente até a confirmação do horário."
- **Contexto Externo**: Preparado para receber `initial_context` (dados já coletados pelo Supervisor).

## 4. Evolução: O Supervisor (Próximo Capítulo)
O Supervisor será o roteador inicial que:
- Identifica a intenção (Agendar, Pagamento, Fornecedor).
- Coleta o nome básico do usuário.
- Faz o "handoff" para o Agente de Agendamento injetando os dados já conhecidos.

---

*Status Atual*: Em transição para Agente Especialista. Lógica de Calendário robusta e imune a ambiguidades de fuso horário.
