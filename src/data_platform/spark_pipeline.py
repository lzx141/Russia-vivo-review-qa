"""Spark implementation of the ODS/DWD/DWS/ADS feedback warehouse."""

from __future__ import annotations

from typing import Any


def create_spark_session(app_name: str, master: str = "local[1]"):
    from pyspark.sql import SparkSession

    return (
        SparkSession.builder.appName(app_name)
        .master(master)
        .config("spark.driver.memory", "512m")
        .config("spark.executor.memory", "512m")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.default.parallelism", "2")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )


def manifest_frame(spark, manifest: dict[str, Any]):
    """Create a one-row manifest without a PythonRDD-backed DataFrame."""
    from pyspark.sql import functions as F

    return spark.range(1).select(
        *[F.lit(value).alias(name) for name, value in manifest.items()]
    )


def _column(df, *names: str):
    from pyspark.sql import functions as F

    for name in names:
        if name in df.columns:
            return F.col(name)
    return F.lit(None)


def _nonempty(column):
    from pyspark.sql import functions as F

    return F.when(
        column.isNull()
        | (F.trim(column.cast("string")) == "")
        | (F.lower(F.trim(column.cast("string"))).isin("nan", "none", "null")),
        F.lit(None),
    ).otherwise(F.trim(column.cast("string")))


def normalize_spark_frame(
    df,
    source_dataset: str,
    dataset_role: str,
    run_id: str,
    *,
    license_name: str | None = None,
):
    from pyspark.sql import functions as F

    platform_raw = F.lower(
        F.coalesce(
            _nonempty(_column(df, "platform", "siteName", "site_name")),
            F.lit("wildberries" if "wb-" in source_dataset else "unknown"),
        )
    )
    platform = (
        F.when(platform_raw.contains("wildberries") | (platform_raw == "wb"), "wildberries")
        .when(platform_raw.contains("ozon"), "ozon")
        .when(platform_raw.contains("yandex") | platform_raw.contains("яндекс"), "yandex_market")
        .otherwise(F.regexp_replace(platform_raw, "[^a-z0-9]+", "_"))
    )
    url = _nonempty(_column(df, "URL", "url"))
    explicit_id = _nonempty(
        _column(df, "source_product_id", "nmId", "nm_id", "SKU", "sku")
    )
    url_id = F.regexp_extract(url, r"(?:catalog/|product/(?:[^/?#]*-)?)(\d{5,})", 1)
    source_product_id = F.coalesce(explicit_id, F.when(url_id != "", url_id))
    product_name = _nonempty(
        _column(df, "product_name", "productName", "name", "imt_name")
    )
    product_slug = F.regexp_replace(F.lower(product_name), r"[^0-9a-zа-яё]+", "-")
    product_slug = F.regexp_replace(product_slug, r"(^-+|-+$)", "")
    product_id = F.when(
        source_product_id.isNotNull(), F.concat_ws(":", platform, source_product_id)
    ).when(
        product_slug != "", F.concat(platform, F.lit(":name:"), product_slug)
    ).otherwise(F.concat(platform, F.lit(":unknown")))
    match_method = (
        F.when(source_product_id.isNotNull(), "source_product_id")
        .when(product_slug != "", "normalized_name")
        .otherwise("unresolved")
    )
    match_confidence = (
        F.when(source_product_id.isNotNull(), F.lit(1.0))
        .when(product_slug != "", F.lit(0.65))
        .otherwise(F.lit(0.0))
    )

    raw_type = F.lower(_nonempty(_column(df, "record_type", "data_type")))
    question = _nonempty(_column(df, "question"))
    record_type = F.when(
        raw_type.isin("qa", "question", "questions") | question.isNotNull(), "question"
    ).otherwise("review")
    review_text = _nonempty(_column(df, "text", "review", "content"))
    text = F.when(record_type == "question", F.coalesce(question, review_text)).otherwise(
        review_text
    )
    answer = _nonempty(_column(df, "answer", "seller_answer"))
    rating = _column(df, "rating", "rate", "productValuation").cast("double")
    date_raw = _nonempty(
        _column(df, "event_date", "publishDate", "publish_date", "date")
    )
    event_timestamp = F.coalesce(
        F.to_timestamp(date_raw),
        F.to_timestamp(date_raw, "dd.MM.yyyy HH:mm"),
        F.to_timestamp(date_raw, "dd.MM.yyyy"),
    )
    event_date = F.to_date(event_timestamp)
    event_month = F.date_format(event_date, "yyyy-MM")
    author = _nonempty(_column(df, "author", "user", "username"))
    source_record_id = _nonempty(
        _column(df, "source_record_id", "review_id", "id")
    )
    record_id = F.coalesce(
        source_record_id,
        F.sha2(
            F.concat_ws(
                "\u001f",
                F.lit(source_dataset),
                platform,
                product_id,
                record_type,
                F.coalesce(event_date.cast("string"), F.lit("")),
                F.coalesce(rating.cast("string"), F.lit("")),
                F.coalesce(text, F.lit("")),
                F.coalesce(answer, F.lit("")),
            ),
            256,
        ),
    )

    normalized = df.select(
        record_id.alias("record_id"),
        F.lit(source_dataset).alias("source_dataset"),
        source_record_id.alias("source_record_id"),
        F.lit(dataset_role).alias("dataset_role"),
        platform.alias("platform"),
        record_type.alias("record_type"),
        product_id.alias("product_id"),
        source_product_id.alias("source_product_id"),
        product_name.alias("product_name"),
        _nonempty(_column(df, "brand", "brandName", "brand_name")).alias("brand"),
        _nonempty(_column(df, "category", "category_label", "subj_name")).alias("category"),
        rating.alias("rating"),
        text.alias("text"),
        answer.alias("answer"),
        author.alias("author"),
        event_date.alias("event_date"),
        event_month.alias("event_month"),
        F.current_timestamp().alias("ingested_at"),
        F.lit(run_id).alias("pipeline_run_id"),
        F.lit(license_name).cast("string").alias("license"),
        _nonempty(_column(df, "source_file")).alias("source_file"),
        match_method.alias("product_match_method"),
        match_confidence.alias("product_match_confidence"),
    )

    letters = F.length(F.regexp_replace(F.coalesce(F.col("text"), F.lit("")), r"[^A-Za-zА-Яа-яЁё]", ""))
    cyrillic = F.length(F.regexp_replace(F.coalesce(F.col("text"), F.lit("")), r"[^А-Яа-яЁё]", ""))
    cyrillic_ratio = F.when(letters > 0, cyrillic / letters).otherwise(F.lit(0.0))
    has_text = F.length(F.trim(F.coalesce(F.col("text"), F.lit("")))) >= 3
    has_answer = F.length(F.trim(F.coalesce(F.col("answer"), F.lit("")))) >= 1
    rating_ok = F.col("rating").between(1.0, 5.0)
    match_ok = F.col("product_match_confidence") >= 0.65
    date_ok = F.col("event_date").isNotNull() & (F.col("event_date") <= F.current_date())
    language_ok = has_text & (cyrillic_ratio >= 0.2)
    is_question = F.col("record_type") == "question"
    score = (
        F.when(has_text, F.when(is_question, 30).otherwise(30)).otherwise(0)
        + F.when(is_question & has_answer, 15).when((~is_question) & rating_ok, 15).otherwise(0)
        + F.when(match_ok, 20).otherwise(0)
        + F.when(date_ok, 15).otherwise(0)
        + F.when(language_ok, 10).otherwise(0)
        + F.lit(10)
    )
    issues = F.array_compact(
        F.array(
            F.when((~is_question) & (~has_text), F.lit("missing_text")),
            F.when(is_question & (~has_text), F.lit("missing_question")),
            F.when(is_question & (~has_answer), F.lit("missing_answer")),
            F.when((~is_question) & (~rating_ok), F.lit("invalid_rating")),
            F.when(~match_ok, F.lit("low_product_match_confidence")),
            F.when(~date_ok, F.lit("invalid_or_missing_date")),
            F.when(has_text & (~language_ok), F.lit("low_cyrillic_ratio")),
        )
    )
    return (
        normalized.withColumn("quality_score", score.cast("int"))
        .withColumn("quality_issues", issues)
        .withColumn(
            "is_rating_eligible", (~is_question) & rating_ok & (F.col("quality_score") >= 55)
        )
        .withColumn("is_text_eligible", language_ok & (F.col("quality_score") >= 70))
        .withColumn("is_trend_eligible", date_ok & (F.col("quality_score") >= 70))
        .withColumn("is_product_eligible", match_ok & (F.col("quality_score") >= 80))
        .withColumn("duplicate_of", F.lit(None).cast("string"))
    )


def build_dws(df):
    from pyspark.sql import functions as F

    return df.groupBy("source_dataset", "platform", "product_id", "event_month").agg(
        F.count("*").alias("total_records"),
        F.sum(F.col("is_rating_eligible").cast("int")).alias("rating_eligible_records"),
        F.sum(F.col("is_text_eligible").cast("int")).alias("text_eligible_records"),
        F.sum(F.col("is_trend_eligible").cast("int")).alias("trend_eligible_records"),
        F.avg(F.when(F.col("is_rating_eligible"), F.col("rating"))).alias("avg_rating"),
        F.sum(F.when(F.col("is_rating_eligible") & (F.col("rating") <= 2), 1).otherwise(0)).alias("negative_records"),
    )


def build_ads(dws_df):
    from pyspark.sql import functions as F

    return dws_df.groupBy("source_dataset", "platform", "event_month").agg(
        F.sum("total_records").alias("total_records"),
        F.sum("rating_eligible_records").alias("rating_eligible_records"),
        F.sum("text_eligible_records").alias("text_eligible_records"),
        F.sum("trend_eligible_records").alias("trend_eligible_records"),
        F.sum("negative_records").alias("negative_records"),
        F.when(
            F.sum("rating_eligible_records") > 0,
            F.sum(F.col("avg_rating") * F.col("rating_eligible_records"))
            / F.sum("rating_eligible_records"),
        ).alias("avg_rating"),
    )


def build_layers(normalized_df) -> dict[str, Any]:
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    normalized_text = F.lower(F.regexp_replace(F.trim(F.col("text")), r"\s+", " "))
    fingerprint = F.sha2(
        F.concat_ws(
            "\u001f",
            F.col("product_id"),
            F.col("record_type"),
            F.coalesce(normalized_text, F.lit("")),
            F.coalesce(F.col("rating").cast("string"), F.lit("")),
        ),
        256,
    )
    ranked = (
        normalized_df.withColumn("record_fingerprint", fingerprint)
        .withColumn(
            "duplicate_rank",
            F.row_number().over(
                Window.partitionBy("record_fingerprint").orderBy(
                    F.desc("quality_score"), F.asc("record_id")
                )
            ),
        )
    )
    invalid = (F.col("quality_score") < 40) | (
        F.col("product_match_method") == "unresolved"
    )
    dwd = ranked.filter((F.col("duplicate_rank") == 1) & (~invalid)).drop(
        "duplicate_rank"
    )
    quarantine = (
        ranked.filter((F.col("duplicate_rank") > 1) | invalid)
        .withColumn(
            "duplicate_of",
            F.when(F.col("duplicate_rank") > 1, F.first("record_id").over(
                Window.partitionBy("record_fingerprint").orderBy(
                    F.desc("quality_score"), F.asc("record_id")
                ).rowsBetween(Window.unboundedPreceding, Window.unboundedFollowing)
            )).otherwise(F.col("duplicate_of")),
        )
        .withColumn("is_rating_eligible", F.lit(False))
        .withColumn("is_text_eligible", F.lit(False))
        .withColumn("is_trend_eligible", F.lit(False))
        .withColumn("is_product_eligible", F.lit(False))
        .drop("duplicate_rank")
    )
    dws = build_dws(dwd)
    ads = build_ads(dws)
    return {"dwd": dwd, "quarantine": quarantine, "dws": dws, "ads": ads}
