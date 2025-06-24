# src/main.py

import csv
import time
import yaml  # Используем PyYAML для чтения конфига
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

# Константы
CONFIG_FILE = "config.yaml"
KEYWORDS_INPUT_FILE = "keywords.csv"
KEYWORDS_OUTPUT_FILE = "keyword_data.csv"

def chunk_list(lst, n):
    """Разделяет список на части (чанки) размером n."""
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def load_config():
    """Загружает конфигурацию из YAML файла."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Ошибка: Файл конфигурации '{CONFIG_FILE}' не найден. "
              f"Скопируйте 'config.yaml.example' в '{CONFIG_FILE}' и заполните его.")
        exit(1)
    except Exception as e:
        print(f"Ошибка при чтении файла конфигурации: {e}")
        exit(1)

def main():
    """Основная функция скрипта."""
    # Загрузка конфигурации
    config = load_config()
    google_ads_config = config['google_ads']
    script_params = config['script_parameters']

    # Загрузка клиента из словаря конфигурации
    try:
        client = GoogleAdsClient.load_from_dict(google_ads_config)
    except Exception as e:
        print(f"Ошибка при инициализации Google Ads клиента: {e}")
        print("Убедитесь, что все поля в 'config.yaml' под ключом 'google_ads' заполнены корректно.")
        exit(1)

    keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")
    customer_id = str(script_params['customer_id'])

    # Читаем ключевые слова из CSV
    keywords = []
    try:
        with open(KEYWORDS_INPUT_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                kw = row['keyword'].strip()
                if kw:
                    keywords.append(kw)
    except FileNotFoundError:
        print(f"Ошибка: Входной файл '{KEYWORDS_INPUT_FILE}' не найден.")
        exit(1)

    if not keywords:
        print("В файле 'keywords.csv' не найдено ключевых слов для обработки.")
        return

    print(f"Найдено {len(keywords)} ключевых слов. Начинаем обработку...")

    # Открываем файл для записи результатов
    with open(KEYWORDS_OUTPUT_FILE, "w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        writer.writerow([
            "keyword",
            "avg_monthly_searches",
            "competition",
            "competition_index",
            "low_top_of_page_bid_micros",
            "high_top_of_page_bid_micros"
        ])

        chunk_size = script_params.get('chunk_size', 10)
        sleep_interval = script_params.get('sleep_interval_seconds', 1)

        for i, chunk in enumerate(chunk_list(keywords, chunk_size)):
            request = client.get_type("GenerateKeywordIdeasRequest")
            request.customer_id = customer_id
            request.language = f"languageConstants/{script_params['language_id']}"

            # Добавляем гео-таргетинги
            for geo_id in script_params['geo_target_ids']:
                request.geo_target_constants.append(f"geoTargetConstants/{geo_id}")

            request.keyword_seed.keywords.extend(chunk)
            request.include_adult_keywords = script_params.get('include_adult_keywords', False)

            try:
                response = keyword_plan_idea_service.generate_keyword_ideas(request=request)
            except GoogleAdsException as ex:
                print(f"Ошибка запроса к API для чанка {i+1}: {ex}")
                # Продолжаем со следующим чанком
                continue

            for idea in response.results:
                metrics = idea.keyword_idea_metrics
                writer.writerow([
                    idea.text,
                    metrics.avg_monthly_searches if metrics else 0,
                    metrics.competition.name if metrics and metrics.competition else "UNSPECIFIED",
                    metrics.competition_index if metrics else 0,
                    metrics.low_top_of_page_bid_micros if metrics else 0,
                    metrics.high_top_of_page_bid_micros if metrics else 0,
                ])

            print(f"Обработан чанк {i+1}/{len(keywords)//chunk_size + 1}. Сохранено {len(response.results)} идей.")
            time.sleep(sleep_interval)

    print(f"\nРабота завершена. Результаты сохранены в файл '{KEYWORDS_OUTPUT_FILE}'.")

if __name__ == "__main__":
    main()
