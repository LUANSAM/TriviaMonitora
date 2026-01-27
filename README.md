# TriviaKm - Controle de Rodagem

Aplicativo web em Flask que replica a ficha de checklist dos veículos e integra diretamente com Supabase para autenticação, banco de dados e armazenamento de imagens.

## Tecnologias

- Flask 3
- Supabase (Auth, Postgres e Storage)
- HTML + CSS copiados do app `relatorio-fotografico`

## Configuração

1. Crie um ambiente virtual e instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
2. Crie um arquivo `.env` com base em `.env.example` e informe a **anon key** do Supabase:
   ```env
   SUPABASE_URL=https://uykchglnflbidcxxgfcq.supabase.co
   SUPABASE_ANON_KEY=sua_anon_key
   FLASK_SECRET_KEY=uma_chave_segura
   ```
3. Execute o servidor local:
   ```bash
   flask --app app run --debug
   ```

## Buckets exigidos

- `avarias` – fotos dos danos vinculados ao relatório.
- `veiculos` – imagem de referência para cada veículo.
- `abastecimentos` – fotos do hodômetro (km) e da nota fiscal.

## Observações

- Perfis com `autorizado = true` na tabela `usuarios` têm o papel de administrador.
- O formulário de checklist grava todos os campos no JSON (`relatorio`) e cria registros em `avaria` quando existirem danos.
- Os abastecimentos salvam o ID como UUID manual para versionar as fotos no bucket.
