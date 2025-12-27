-- 利用可能な全文検索設定を確認
SELECT cfgname FROM pg_ts_config;

-- pg_bigm拡張が利用可能か確認
SELECT * FROM pg_available_extensions WHERE name = 'pg_bigm';
