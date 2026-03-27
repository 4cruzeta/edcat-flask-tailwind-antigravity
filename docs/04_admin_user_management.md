# Plano de Implementação: Gestão de Usuários V2 (Admin)

Este documento registra as decisões arquitetônicas adotadas para recriar o módulo de Administração de Usuários, migrando-o do Firebase Client (V1) para uma integração robusta via Firebase Admin SDK + Flask Middleware na versão 2.

## Melhorias Implementadas vs V1

### 1. Hard Delete (Exclusão Definitiva via Modal Confirm)
- Na V1 o sistema permitia apenas alterar o *"Status"* para Inativo, gerando lixo na base de Autenticação do Google Cloud.
- Na V2, projetou-se um fluxo restrito para **Deletar Definitivamente**, requerendo confirmação (Modo Exclusão com Botões de Perigo vermelho) na interface `admin_home`. O comando limpa o registro na base `auth` principal e dropa a linha do Banco `firestore`.

### 2. Modais via Pure Tailwind (Flowbite) ao invés de JS Intervencionista
- Antigamente (V1): O arquivo trazia funções extensas (`function openEditModal(button) { ... }`) que procuravam IDs no DOM e destrancavam div ocultas usando lógica braçal.
- Agora (V2): Usaremos exclusivamente a interface declarativa do *Flowbite* (`data-modal-target="editModal"` e `data-modal-toggle="editModal"`), resultando na limpeza total das funções JS e alinhamento AAA de acessibilidade.

### 3. Integração "Secret Manager" no Switch de Cargos (Roles)
- A lógica de distribuição de privilégios (`admin`, `tester`) durante a criação continua protegida e validada pelas Strings armazenadas de forma oculta nos cofres do Google Cloud Secret Manager. Contudo, ela ganha mais velocidade rodando através da instância global do Flask Factory.

### Backend Routing (edcat_root/views.py)
A interface de gerenciamento repousa sobre 4 endpoints unificados:
- `GET /admin_home`: Extração de todos os usuários (`db.collection('users').stream()`) em massa e envio para engine Jinja do template.
- `POST /create_user`: Orquestra o Auth Admin SDK e persiste o snapshot no banco.
- `POST /admin/update_user/<uid>`: Salva rapidamente alterações inline de Perfil ou Roles da UI.
- `POST /admin/delete_user/<uid>`: (Novo) Rota exclusiva para Hard Delete.
- `GET /api/user/<uid>`: Micro-API para preencher modais dinamicamente.
