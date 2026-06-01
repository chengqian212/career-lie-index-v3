# Streamlit Cloud + Supabase Deployment

## Streamlit Cloud

Deploy with:

- Repository: `career_lie_index_agent`
- Branch: `main`
- Main file path: `v3/app.py`

`requirements.txt` is intentionally placed in `v3/`, next to `app.py`.

Add these secrets in Streamlit Cloud app settings:

```toml
DEEPSEEK_API_KEY = "your_deepseek_api_key"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"
MAX_ROUNDS = "8"
MIN_FOLLOWUP_ROUNDS = "5"
TEMPERATURE = "0.2"

SUPABASE_URL = "https://your-project-ref.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "your_service_role_key"
SUPABASE_OUTPUTS_TABLE = "output_files"
```

## Supabase

1. Create a free Supabase project.
2. Open SQL Editor.
3. Run the SQL in `v3/supabase_schema.sql`.
4. Copy `Project URL` into `SUPABASE_URL`.
5. Copy `service_role` key into `SUPABASE_SERVICE_ROLE_KEY`.

The app automatically syncs newly generated report/log files to Supabase when
Supabase credentials are configured.

## Upload Existing `outputs`

After setting Supabase credentials locally in `.env`, run:

```bash
cd v3
python scripts/upload_outputs_to_supabase.py
```

This uploads all files under `v3/outputs`, excluding `.gitkeep`.
