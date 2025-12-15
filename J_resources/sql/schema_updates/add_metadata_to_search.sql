-- メタデータを検索可能にするためのスキーマ更新
-- 実行場所: Supabase SQL Editor
-- 目的: weekly_schedule等のメタデータを全文検索とベクトル検索の対象にする

BEGIN;

-- 1. documentsテーブルにメタデータ検索用のテキストカラムを追加
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS metadata_searchable_text TEXT;

-- 2. メタデータからテキストを抽出する関数
CREATE OR REPLACE FUNCTION extract_searchable_metadata(metadata_json JSONB)
RETURNS TEXT AS $$
DECLARE
    searchable_parts TEXT[] := ARRAY[]::TEXT[];
    day_item JSONB;
    class_item JSONB;
    period_item JSONB;
    text_block JSONB;
    event_text TEXT;
    note_text TEXT;
BEGIN
    -- weekly_schedule の展開
    IF metadata_json ? 'weekly_schedule' THEN
        FOR day_item IN SELECT * FROM jsonb_array_elements(metadata_json->'weekly_schedule')
        LOOP
            -- 日付と曜日
            IF day_item ? 'date' THEN
                searchable_parts := array_append(searchable_parts, day_item->>'date');
            END IF;
            IF day_item ? 'day_of_week' THEN
                searchable_parts := array_append(searchable_parts, day_item->>'day_of_week');
            END IF;
            IF day_item ? 'day' THEN
                searchable_parts := array_append(searchable_parts, (day_item->>'day') || '曜日');
            END IF;

            -- イベント
            IF day_item ? 'events' THEN
                FOR event_text IN SELECT * FROM jsonb_array_elements_text(day_item->'events')
                LOOP
                    searchable_parts := array_append(searchable_parts, event_text);
                END LOOP;
            END IF;

            -- ノート
            IF day_item ? 'note' THEN
                note_text := day_item->>'note';
                IF note_text IS NOT NULL AND note_text != '' THEN
                    searchable_parts := array_append(searchable_parts, note_text);
                END IF;
            END IF;

            -- クラススケジュール
            IF day_item ? 'class_schedules' THEN
                FOR class_item IN SELECT * FROM jsonb_array_elements(day_item->'class_schedules')
                LOOP
                    -- クラス名
                    IF class_item ? 'class' THEN
                        searchable_parts := array_append(searchable_parts, class_item->>'class');
                    END IF;

                    -- subjects配列
                    IF class_item ? 'subjects' THEN
                        FOR event_text IN SELECT * FROM jsonb_array_elements_text(class_item->'subjects')
                        LOOP
                            searchable_parts := array_append(searchable_parts, event_text);
                        END LOOP;
                    END IF;

                    -- periods配列
                    IF class_item ? 'periods' THEN
                        FOR period_item IN SELECT * FROM jsonb_array_elements(class_item->'periods')
                        LOOP
                            IF period_item ? 'subject' THEN
                                searchable_parts := array_append(searchable_parts, period_item->>'subject');
                            END IF;
                            IF period_item ? 'time' THEN
                                searchable_parts := array_append(searchable_parts, period_item->>'time');
                            END IF;
                        END LOOP;
                    END IF;
                END LOOP;
            END IF;
        END LOOP;
    END IF;

    -- text_blocks の展開
    IF metadata_json ? 'text_blocks' THEN
        FOR text_block IN SELECT * FROM jsonb_array_elements(metadata_json->'text_blocks')
        LOOP
            IF text_block ? 'title' THEN
                searchable_parts := array_append(searchable_parts, text_block->>'title');
            END IF;
            IF text_block ? 'content' THEN
                searchable_parts := array_append(searchable_parts, text_block->>'content');
            END IF;
        END LOOP;
    END IF;

    -- special_events の展開
    IF metadata_json ? 'special_events' THEN
        FOR event_text IN SELECT * FROM jsonb_array_elements_text(metadata_json->'special_events')
        LOOP
            searchable_parts := array_append(searchable_parts, event_text);
        END LOOP;
    END IF;

    -- important_notes の展開
    IF metadata_json ? 'important_notes' THEN
        FOR note_text IN SELECT * FROM jsonb_array_elements_text(metadata_json->'important_notes')
        LOOP
            searchable_parts := array_append(searchable_parts, note_text);
        END LOOP;
    END IF;

    -- basic_info の展開
    IF metadata_json ? 'basic_info' THEN
        FOR event_text IN SELECT value::TEXT FROM jsonb_each_text(metadata_json->'basic_info')
        LOOP
            IF event_text IS NOT NULL AND event_text != '' THEN
                searchable_parts := array_append(searchable_parts, event_text);
            END IF;
        END LOOP;
    END IF;

    RETURN array_to_string(searchable_parts, ' ');
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 3. トリガー関数を更新してメタデータも含める
CREATE OR REPLACE FUNCTION documents_tsvector_update_trigger()
RETURNS TRIGGER AS $$
DECLARE
    metadata_text TEXT;
BEGIN
    -- メタデータから検索可能テキストを抽出
    metadata_text := extract_searchable_metadata(COALESCE(NEW.metadata, '{}'::jsonb));
    NEW.metadata_searchable_text := metadata_text;

    -- full_text + metadata を tsvector に変換
    NEW.full_text_tsv := to_tsvector('simple',
        COALESCE(NEW.full_text, '') || ' ' || COALESCE(metadata_text, '')
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 4. トリガーを再作成
DROP TRIGGER IF EXISTS tsvector_update_trigger ON documents;
CREATE TRIGGER tsvector_update_trigger
    BEFORE INSERT OR UPDATE OF full_text, metadata
    ON documents
    FOR EACH ROW
    EXECUTE FUNCTION documents_tsvector_update_trigger();

-- 5. 既存データのmetadata_searchable_textとtsvectorを更新
UPDATE documents
SET metadata_searchable_text = extract_searchable_metadata(COALESCE(metadata, '{}'::jsonb)),
    full_text_tsv = to_tsvector('simple',
        COALESCE(full_text, '') || ' ' ||
        extract_searchable_metadata(COALESCE(metadata, '{}'::jsonb))
    )
WHERE processing_status = 'completed';

-- 6. インデックスが存在することを確認
CREATE INDEX IF NOT EXISTS idx_documents_full_text_tsv ON documents USING GIN(full_text_tsv);
CREATE INDEX IF NOT EXISTS idx_documents_metadata_searchable ON documents USING GIN(to_tsvector('simple', metadata_searchable_text));

COMMIT;

-- 実行確認クエリ
-- SELECT file_name, metadata_searchable_text FROM documents WHERE metadata_searchable_text LIKE '%12月5日%' OR metadata_searchable_text LIKE '%委員会%';
