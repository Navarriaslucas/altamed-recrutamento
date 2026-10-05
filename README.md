# Recrutamento — Grupo Altamed

Plataforma de recrutamento em Flask: mural de vagas, candidatura (dados + questionário de cultura + teste DISC + LGPD) e painel administrativo (dashboard, Kanban por vaga, usuários).

## Rodar localmente
```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export SECRET_KEY="uma-chave-longa-e-aleatoria"
export SENHA_INICIAL="defina-uma-senha-forte"   # senha dos 3 usuários criados na 1ª execução
flask --app app run --debug
```
Abra http://127.0.0.1:5000 e entre em **Acesso Administrador**.

## Estrutura
- `app.py` — rotas, modelos (User, Vaga, Candidato) e regras
- `templates/base.html` (sem menu) · `base_top.html` (menu superior) · `base_admin.html` (menu lateral)
- `data/disc.json` — 26 perguntas e perfis, extraídos da planilha DISC
- `static/` — CSS, JS (Kanban/DISC) e logo

## Publicar no GitHub
```bash
git remote add origin https://github.com/SEU-USUARIO/altamed-recrutamento.git
git branch -M main
git push -u origin main
```
