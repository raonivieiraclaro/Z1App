# Campanhas Meta Ads no Z1 Prospect IA

Abra `/meta-ads` pelo painel administrativo. Todas as rotas usam o login existente.

## Fluxo disponível

1. Preencha nome, objetivo, categorias especiais aplicáveis e planejamento interno.
2. Salve e revise o rascunho. Isso funciona mesmo sem credenciais e não chama a Meta.
3. Quando houver uma conta configurada, marque a confirmação e crie a campanha pausada.
4. Conclua conjuntos, público, orçamento e anúncios no Gerenciador de Anúncios antes de veicular.

O módulo cria **somente o objeto campanha**, sempre `PAUSED`. Não cria conjuntos,
criativos ou anúncios e não tem uma rota para ativar campanhas ou alterar orçamento.
Anotações internas não são transmitidas à Meta. Não há envio de mensagens.

## Configuração protegida no Render

Use as variáveis do serviço `z1-prospect-ia`; não coloque tokens no código, em arquivos
versionados, no painel do app ou em conversas.

| Variável | Uso |
| --- | --- |
| `META_ADS_ACCESS_TOKEN` | Token Meta autorizado com `ads_management` e acesso à conta de anúncios. Para leitura, autorize também `ads_read`. Não reutilizar automaticamente o token do WhatsApp. |
| `META_AD_ACCOUNT_ID` | ID numérico da conta de anúncios, aceitando prefixo `act_`. |
| `META_ADS_GRAPH_VERSION` | Versão da API de anúncios. Padrão: `v25.0`, separada da API de mensagens. |
| `Z1_ADS_DB_PATH` | Caminho SQLite opcional, padrão `/tmp/z1_ads.sqlite3`. Use um disco persistente para durabilidade. |

Após salvar variáveis e concluir o deploy, use **Verificar acesso à conta**.
A consulta de leitura bem-sucedida não garante permissão de criação nem aprovação de anúncios.
Esta entrega não gera token, não altera permissões da Meta e não cria campanhas reais.
O acesso à conta de desenvolvedor e a autorização dos ativos devem estar liberados.

## Segurança e limites

- O backend impõe `PAUSED` mesmo após carregar o rascunho; campos adicionais como `status=ACTIVE` são rejeitados.
- Mutações exigem autenticação e `Origin` igual ao serviço. Credenciais nunca aparecem nas respostas.
- Cada rascunho tem no máximo uma tentativa de escrita na Meta. Envios concorrentes são bloqueados por transação SQLite.
- Se uma resposta for incerta, o rascunho fica marcado para conferência manual na Meta e não é reenviado automaticamente.
- Rascunhos ficam vinculados à conta revisada. Uma mudança de conta exige nova revisão.
- Sem disco persistente, o histórico pode ser perdido em deploys e reinícios. Baixe uma cópia no painel.
- O histórico mostra as últimas 100 preparações. Não inserir dados pessoais nas anotações.

## Verificação local

Instale as dependências de `requirements.txt` e `httpx` para testes; execute
`python -m unittest -v test_meta_ads.py`. As chamadas à Meta são simuladas e não geram gastos.

Referência primária do payload: exemplo oficial da Meta
https://github.com/facebook/facebook-python-business-sdk/blob/main/examples/AdAccountCampaignsPost.py
e campos do SDK: https://github.com/meta/facebook-python-business-sdk/blob/main/facebook_business/adobjects/campaign.py
