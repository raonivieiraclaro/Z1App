# Integrações Z1 Prospect IA

## Render — Environment
Configure valores secretos exclusivamente no Render; nunca publique tokens no GitHub.

- OPENAI_API_KEY: chave da OpenAI (já utilizada pelo consultor)
- META_APP_SECRET: segredo do aplicativo Meta Developers, para validar a assinatura X-Hub-Signature-256
- META_VERIFY_TOKEN: string privada criada pelo administrador e informada também no Meta Developers
- WHATSAPP_ACCESS_TOKEN: token oficial do WhatsApp Cloud API, com permissões adequadas
- WHATSAPP_PHONE_NUMBER_ID: identificador do número comercial da Cloud API
- META_GRAPH_VERSION: versão Graph API suportada pela sua aplicação (opcional)
- Z1_WHATSAPP_AUTO_REPLY: false por padrão; defina true somente depois de testar e confirmar consentimento
- Z1_DB_PATH: caminho para SQLite em disco persistente, se disponível

## Meta Developers
Callback URL: https://z1-prospect-ia.onrender.com/webhooks/meta
Verify token: mesmo valor de META_VERIFY_TOKEN.

Assine os campos relevantes do WhatsApp Business Account, configure o número e teste mensagens recebidas. A verificação GET e assinatura POST já são implementadas. O endpoint de status do administrador é /integracoes.

## Limites atuais
- O webhook de Instagram valida a assinatura e reconhece eventos, mas não processa DMs nem envia respostas.
- WhatsApp responde apenas a mensagens de texto recebidas, quando explicitamente habilitado; não envia mensagens frias.
- O webhook ainda não tem armazenamento de IDs processados, fila durável, política de retry ou processamento em background. Não habilite resposta automática em produção antes dessas melhorias.
- Não existe integração de criação de cadastro no escritório Zyone sem API/documentação autorizada.
- SQLite em /tmp não é durável no Render. Configure armazenamento persistente antes de cadastrar conteúdo que não pode ser perdido.
- Não insira dados pessoais ou informações sensíveis na base de conhecimento.
