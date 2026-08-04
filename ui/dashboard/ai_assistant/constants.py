# ui/dashboard/ai_assistant/constants.py
"""Myanmar texts and configuration constants"""

MYANMAR_TEXTS = {
    "no_sales": "ယနေ့နှင့် မနေ့က ရောင်းအား မရှိပါ။",
    "sales_up": "ယနေ့ရောင်းအားသည် မနေ့ကထက် {change}% မြင့်တက်နေသည်။",
    "sales_down": "ယနေ့ရောင်းအားသည် မနေ့ကထက် {change}% ကျဆင်းနေသည်။",
    "sales_stable": "ယနေ့ရောင်းအားသည် မနေ့ကနှင့် ဆင်တူနေသည်။",
    "weekly_up": "ဒီအပတ်ရောင်းအားသည် ပြီးခဲ့တဲ့အပတ်ထက် {change}% မြင့်တက်နေသည်။",
    "weekly_down": "ဒီအပတ်ရောင်းအားသည် ပြီးခဲ့တဲ့အပတ်ထက် {change}% ကျဆင်းနေသည်။",
    "weekly_stable": "ဒီအပတ်ရောင်းအားသည် ပြီးခဲ့တဲ့အပတ်နှင့် ဆင်တူနေသည်။",
    "monthly_up": "ဒီလရောင်းအားသည် ပြီးခဲ့တဲ့လထက် {change}% မြင့်တက်နေသည်။",
    "monthly_down": "ဒီလရောင်းအားသည် ပြီးခဲ့တဲ့လထက် {change}% ကျဆင်းနေသည်။",
    "monthly_stable": "ဒီလရောင်းအားသည် ပြီးခဲ့တဲ့လနှင့် ဆင်တူနေသည်။",
    "top_category": "ပြီးခဲ့သည့် {days} ရက်အတွင်း အရောင်းရဆုံး အမျိုးအစား",
    "stock_alert": "စတော့သတိပေးချက်",
    "stock_ok": "ပစ္စည်းအားလုံး စတော့အလုံအလောက်ရှိသည်။",
    "best_seller": "ယနေ့ အရောင်းရဆုံးပစ္စည်း",
    "top_products": "ထိပ်ဆုံးရောင်းရဆုံး ပစ္စည်းများ",
    "high_discount": "ယနေ့ လျှော့စျေးနှုန်း မြင့်မားနေသည်",
    "peak_hour_sales": "ယနေ့ အရောင်းအများဆုံးအချိန် {hour}:00",
    "repeat_customers": "ပြန်လည်ဝယ်ယူသူ {count} ဦး ({pct}%)",
    "forecast_7d": "ရက် ၇ ခန့်မှန်းချက်",
    "forecast_14d": "ရက် ၁၄ ခန့်မှန်းချက်",
    "forecast_30d": "ရက် ၃၀ ခန့်မှန်းချက်",
}

# Default refresh interval in milliseconds
DEFAULT_REFRESH_INTERVAL = 60000  # 60 seconds
NOTIFICATION_INTERVAL = 300000  # 5 minutes

# Emoji map for fallback icons
EMOJI_ICONS = {
    "trending_up": "📈",
    "trending_down": "📉",
    "bar_chart": "📊",
    "trophy": "🏆",
    "warning": "⚠️",
    "check_circle": "✅",
    "local_fire_department": "🔥",
    "percent_discount": "🏷️",
    "clock": "🕐",
    "groups": "👥",
    "analytics": "📊",
    "calendar": "📅",
    "calendar_month": "📆",
    "credit_card": "💳",
    "package": "📦",
    "star": "⭐",
    "bolt": "⚡",
    "chart": "📈",
}

# Date range options
DATE_RANGES = [
    "Today",
    "Yesterday",
    "This Week",
    "This Month",
    "Last 7 Days",
    "Last 30 Days",
    "Custom Range",
]

# Refresh interval options
REFRESH_INTERVALS = ["30s", "60s", "120s", "300s", "Off"]