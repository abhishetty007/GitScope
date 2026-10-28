CREATE TABLE "gitscope_rate_limit_windows" (
    "bucket" VARCHAR(64) NOT NULL,
    "client_key" CHAR(64) NOT NULL,
    "window_start" TIMESTAMPTZ(0) NOT NULL,
    "request_count" INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT "gitscope_rate_limit_windows_pkey"
        PRIMARY KEY ("bucket", "client_key", "window_start"),
    CONSTRAINT "gitscope_rate_limit_windows_count_positive"
        CHECK ("request_count" > 0)
);

CREATE INDEX "gitscope_rate_limit_windows_window_start_idx"
    ON "gitscope_rate_limit_windows"("window_start");
