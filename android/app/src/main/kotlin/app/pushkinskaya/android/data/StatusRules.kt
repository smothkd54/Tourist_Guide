package app.pushkinskaya.android.data

/** Only these two values get a badge. A missing status (the Flask API sends none yet) means "nothing to show". */
fun isNotOpen(status: String?): Boolean = status == "closed" || status == "temporarily_closed"
