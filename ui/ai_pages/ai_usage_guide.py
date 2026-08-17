"""Built-in, bilingual-friendly usage guide for the ZAY POS application."""


class ProjectUsageGuide:
    HELP_WORDS = (
        "how to", "how do i", "how can i", "usage", "user guide", "manual",
        "instructions", "help with", "အသုံးပြုပုံ", "သုံးစွဲပုံ", "ဘယ်လိုသုံး",
        "ဘယ်လိုလုပ်", "လမ်းညွှန်", "အကူအညီ",
    )

    TOPICS = (
        ("cash_sessions", ("cash session", "cash-session", "ငွေစာရင်း")),
        ("performance", ("performance", "စွမ်းဆောင်ရည်")),
        ("documents", ("employee document", "documents tab", "စာရွက်စာတမ်း")),
        ("commission", ("commission", "advance", "ကော်မရှင်", "ကြိုတင်လစာ")),
        ("payroll", ("payroll", "salary", "လစာ")),
        ("attendance", ("attendance", "check-in", "check in", "တက်ရောက်", "အလုပ်ဝင်")),
        ("leave", ("leave", "ခွင့်")),
        ("shifts", ("shift", "အလုပ်ချိန်")),
        ("employees", ("employee", "staff", "ဝန်ထမ်း")),
        ("credit", ("credit", "debt", "အကြွေး")),
        ("customers", ("customer", "ဖောက်သည်")),
        ("inventory", ("inventory", "stock in", "stock out", "warehouse", "စတော့")),
        ("products", ("product", "barcode", "sku", "ပစ္စည်း")),
        ("receipts", ("receipt", "refund", "ပြေစာ", "ပြန်အမ်း")),
        ("expenses", ("expense", "ကုန်ကျစရိတ်", "အသုံးစရိတ်")),
        ("reports", ("report", "အစီရင်ခံစာ")),
        ("sales", ("sale", "checkout", "cart", "ရောင်း", "အရောင်း")),
        ("permissions", ("permission", "role", "admin", "manager", "cashier", "viewer", "ခွင့်ပြုချက်")),
        ("users", ("user account", "login account", "အသုံးပြုသူ")),
        ("backup", ("backup", "restore", "factory reset", "အရန်", "ပြန်ယူ")),
        ("settings", ("setting", "zkteco", "database connection", "ပြင်ဆင်မှု")),
        ("ai", ("ai page", "ai chat", "ai assistant")),
    )

    GUIDES = {
        "sales": """🛒 **Sales / Checkout အသုံးပြုပုံ**

1. Sales page ကိုဖွင့်ပြီး Product၊ SKU သို့မဟုတ် Barcode နဲ့ပစ္စည်းရွေးပါ။
2. Quantity၊ discount နဲ့ customer ကိုလိုအပ်သလိုသတ်မှတ်ပါ။
3. Checkout နှိပ်ပြီး Cash/Card/QR/Credit payment type ရွေးပါ။
4. Payment amount စစ်ပြီး sale ကိုအတည်ပြုပါ။
5. ပြီးသွားတဲ့ invoice ကို Receipts page မှာ ပြန်ကြည့်/print လုပ်နိုင်ပါတယ်။

Credit sale လုပ်မယ်ဆိုရင် customer ရွေးထားပြီး credit permission ရှိရပါမယ်။""",
        "products": """📦 **Products အသုံးပြုပုံ**

• Add Product နဲ့ Name, SKU, Barcode, Price, Cost, Category နဲ့ stock settings ဖြည့်ပါ။
• Table မှာ product ရွေးပြီး Edit/Delete လုပ်နိုင်ပါတယ် (permission လိုအပ်သည်)။
• ပုံတင်ခြင်း၊ category/supplier ချိတ်ခြင်းနဲ့ low-stock level သတ်မှတ်နိုင်ပါတယ်။
• Barcode/SKU တစ်ခုချင်းစီ unique ဖြစ်ရပါမယ်။""",
        "inventory": """🏬 **Inventory အသုံးပြုပုံ**

• Current Stock မှာ လက်ရှိ quantity နဲ့ location ကိုကြည့်ပါ။
• Stock In ကို ဝယ်ယူ/လက်ခံရရှိသည့်ပစ္စည်းထည့်ရာမှာသုံးပါ။
• Stock Out ကို ပျက်စီး/အသုံးပြု/အခြားထုတ်ယူမှုအတွက်သုံးပါ။
• Adjustment ကို physical count နဲ့ system quantity မကိုက်ချိန် reason ဖြင့်ပြင်ရန်သုံးပါ။
• Low Stock/Expiry tabs ကို reorder နဲ့ expiry စစ်ရန်သုံးပါ။""",
        "receipts": """🧾 **Receipts အသုံးပြုပုံ**

• Date၊ invoice၊ customer နဲ့ payment type အလိုက်ရှာပါ။
• Row ကိုဖွင့်ပြီး sale items, totals, discount နဲ့ payment ကိုစစ်ပါ။
• Print Receipt နဲ့ပြန်ထုတ်နိုင်ပါတယ်။
• Refund permission ရှိသူသာ refund လုပ်နိုင်ပြီး stock/customer balance ကို ပြန်ညှိပေးပါတယ်။""",
        "customers": """👥 **Customers အသုံးပြုပုံ**

• Add Customer နဲ့ အမည်၊ ဖုန်း၊ လိပ်စာနဲ့ credit information ဖြည့်ပါ။
• Search နဲ့ customer profile၊ purchase history နဲ့ balance ကိုကြည့်ပါ။
• Credit sale မလုပ်မီ customer record မှန်ကန်စွာရွေးထားပါ။""",
        "credit": """💳 **Credit / Debt အသုံးပြုပုံ**

1. Credit customer နဲ့ invoice ကိုရွေးပါ။
2. Record Payment မှာ Amount, Date, Method, Reference နဲ့ Note ဖြည့်ပါ။
3. Invoice တစ်ခုကိုရွေးပြီးပေးချေခြင်း သို့မဟုတ် Auto Allocate နဲ့ အဟောင်းဆုံး invoices မှစခွဲဝေနိုင်ပါတယ်။
4. Amount က balance ထက်မကျော်ရပါ။ အပြည့်ပေးပြီးရင် Paid၊ မပြည့်ရင် Partial ဖြစ်ပါတယ်။""",
        "expenses": """💸 **Expenses အသုံးပြုပုံ**

• Add Expense မှာ category၊ description၊ amount၊ date နဲ့ payment method ဖြည့်ပါ။
• Receipt/attachment ရှိရင်တွဲထားနိုင်ပါတယ်။
• Category နဲ့ date filters သုံးပြီးရှာနိုင်ပါတယ်။
• Salary payroll ကို Mark Paid လုပ်ရင် Salary expense အလိုအလျောက်ဖန်တီးနိုင်ပါတယ်။""",
        "reports": """📊 **Reports အသုံးပြုပုံ**

• လိုချင်တဲ့ report type နဲ့ date range ရွေးပါ။
• Branch/category/payment filters ကိုလိုအပ်သလိုသုံးပါ။
• Screen totals ကိုစစ်ပြီး Excel/CSV/PDF export ရှိသည့် report များကိုထုတ်နိုင်ပါတယ်။
• Report result က current database နဲ့ရွေးထားတဲ့ date range ပေါ်မူတည်ပါတယ်။""",
        "employees": """👤 **Employees အသုံးပြုပုံ**

• Employees tab မှာ profile၊ Employee ID၊ POS account၊ department/branch နဲ့ photo ကိုစီမံပါ။
• Attendance မှာ K20 sync၊ correction၊ issue/status/date filters သုံးပါ။
• Shifts မှာ shift definitions ဖန်တီးပြီး effective date နဲ့ assign ပါ။
• Payroll၊ Leave၊ Documents၊ Advances & Commission၊ Performance နဲ့ Cash Sessions ကို သက်ဆိုင်ရာ tabs မှာစီမံပါ။
• မြင်ရ/ပြင်ရသည့် tabs နဲ့ buttons က login role permissions ပေါ်မူတည်ပါတယ်။""",
        "attendance": """🕒 **Attendance အသုံးပြုပုံ**

• Sync K20 နဲ့ configured devices မှ punches ကိုသွင်းပါ။
• Date range၊ employee၊ Missing Check-in/Out၊ Before/After Shift နဲ့ Status filters သုံးပါ။
• Add / Correct နဲ့ manual correction လုပ်ရာမှာ reason ထည့်ပါ။
• Late calculation အတွက် employee ကို effective shift assign လုပ်ထားရပါမယ်။""",
        "shifts": """🗓️ **Shifts အသုံးပြုပုံ**

• New Shift နဲ့ start/end time၊ break နဲ့ overnight ကိုသတ်မှတ်ပါ။
• Assign Shift နဲ့ employee နဲ့ effective-from date ချိတ်ပါ။
• Assignment row ကိုရွေးပြီး Edit Assignment သို့မဟုတ် Delete Assignment သုံးနိုင်ပါတယ်။
• Date တစ်ရက်တည်းမှာ employee တစ်ယောက်အတွက် assignment တစ်ခုပဲရှိနိုင်ပါတယ်။""",
        "leave": """🏖️ **Leave အသုံးပြုပုံ**

• New Leave Request မှာ employee၊ type၊ start/end dates နဲ့ reason ဖြည့်ပါ။
• Pending request ကို permission ရှိသူက Approve သို့မဟုတ် Reject လုပ်ပါ။
• Approved leave က attendance category calculation နဲ့ချိတ်ဆက်ပါတယ်။""",
        "payroll": """💵 **Payroll အသုံးပြုပုံ**

• Month ကို YYYY-MM ပုံစံရွေးပြီး Create Payroll နှိပ်ပါ။
• Basic salary + allowance + overtime + bonus − deductions နဲ့ Net Salary တွက်ပါတယ်။
• Draft row ကိုရွေးပြီး Mark Paid လုပ်ရင် Paid status နဲ့ Salary expense ဖန်တီးပါတယ်။
• Employee တစ်ယောက်အတွက် တစ်လတည်း payroll တစ်ခုပဲဖန်တီးနိုင်ပါတယ်။""",
        "documents": """📄 **Employee Documents အသုံးပြုပုံ**

• Employee၊ document type/no၊ issued/expiry dates၊ file နဲ့ notes ဖြည့်ပါ။
• Search/type/expiry filters နဲ့ရှာပါ။
• လက်ရှိ database မှာ document file path ကိုမှတ်ထားတာကြောင့် မူရင်း file ကိုမရွှေ့/မဖျက်သင့်ပါ။""",
        "commission": """💰 **Advances & Commission အသုံးပြုပုံ**

• Salary Advance နဲ့ employee၊ date၊ amount ထည့်ပါ။
• Record Repayment နဲ့ပြန်ဆပ်ငွေသွင်းပြီး Outstanding/Repaid status ကို update လုပ်ပါ။
• Commission Rule မှာ Rate % နဲ့ Minimum Target သတ်မှတ်ပါ။
• Commission result ကို Performance tab မှာကြည့်နိုင်ပါတယ်။""",
        "performance": """📈 **Performance အသုံးပြုပုံ**

• Date range၊ employee search နဲ့ branch filter သတ်မှတ်ပါ။
• Sales, Revenue, Refunds, Discounts, Target, Rate နဲ့ Commission ကိုကြည့်ပါ။
• Employee ကို POS user account ချိတ်ထားမှ သူ့ sales ကိုမှန်ကန်စွာတွက်နိုင်ပါတယ်။""",
        "cash_sessions": """💵 **Cash Sessions အသုံးပြုပုံ**

• အလုပ်စချိန် Open Session မှာ employee နဲ့ Opening Cash ဖြည့်ပါ။
• ပိတ်ချိန် row ရွေးပြီး Close Session မှာ Actual Cash ဖြည့်ပါ။
• Expected = Opening Cash + completed cash sales ဖြစ်ပြီး Difference = Actual − Expected ဖြစ်ပါတယ်။
• Employee တစ်ယောက်မှာ Open session တစ်ခုပဲရှိနိုင်ပါတယ်။""",
        "ai": """🤖 **AI Pages အသုံးပြုပုံ**

• Dashboard မှာ business overview ကြည့်ပါ။
• AI Chat မှာ English/Myanmar နဲ့ sales, inventory, customer, credit, expense, receipt နဲ့ employee queries မေးပါ။
• Enter = Send၊ Shift+Enter = new line ဖြစ်ပါတယ်။
• Quick actions၊ Recent Prompts၊ Retry၊ Copy၊ Export နဲ့ /help commands သုံးနိုင်ပါတယ်။
• AI က login role permissions ထက်ကျော်ပြီး data မပြပါ။""",
        "users": """👤 **Users အသုံးပြုပုံ**

• Settings > Users မှာ login account ဖန်တီး/ပြင်/ပိတ်နိုင်ပါတယ်။
• Username unique ဖြစ်ရပြီး လိုအပ်တဲ့ role ရွေးပါ။
• Employee sales/performance ချိတ်လိုရင် Employee Profile ထဲမှာ POS account ကို link လုပ်ပါ။""",
        "permissions": """🔐 **Roles & Permissions အသုံးပြုပုံ**

• Admin = full access။ Manager = daily operations/employee management။
• Cashier = sales-focused access နဲ့ AI Pages။ Viewer = read-only access။
• Role Management မှာ View/Manage permissions ကိုသီးခြားသတ်မှတ်နိုင်ပါတယ်။
• Permission ပြောင်းပြီးနောက် logout/login သို့မဟုတ် app restart လုပ်ပါ။""",
        "settings": """⚙️ **Settings အသုံးပြုပုံ**

• Shop, receipt, language/theme, database, users, updates နဲ့ integrations ကို သက်ဆိုင်ရာ settings pages မှာပြင်ပါ။
• ZKTeco Devices မှာ Device ID, IP, Port, Comm Key, Active status နဲ့ employee mappings သတ်မှတ်ပါ။
• Edit Settings permission ရှိသူသာ configuration ပြောင်းသင့်ပါတယ်။""",
        "backup": """🛡️ **Backup / Restore အသုံးပြုပုံ**

• Backup ကို data ပြောင်းလဲမှုကြီးမလုပ်မီ ပုံမှန်ဖန်တီးပါ။
• Restore က လက်ရှိ data ကို backup state ပြန်ထားနိုင်တာကြောင့် file/date မှန်ကြောင်းအရင်စစ်ပါ။
• Factory Reset က data ဖျက်နိုင်တဲ့ destructive action ဖြစ်ပြီး Admin permission နဲ့ confirmation လိုပါတယ်။""",
    }

    # Extra operational notes are kept separate from the short guide so the
    # assistant can stay easy to maintain while still returning a complete,
    # step-by-step answer to the user.
    DETAILS = {
        "sales": """**မလုပ်ဆောင်မီ** Product stock/price နဲ့ cashier session ဖွင့်ထားမှုကိုစစ်ပါ။\n\n**အသေးစိတ် Workflow**\n1. Search သို့မဟုတ် barcode scanner နဲ့ item ထည့်ပါ။\n2. Cart row မှ quantity ပြင်ပြီး item/order discount ကိုစစ်ပါ။\n3. Customer လိုအပ်လျှင် checkout မတိုင်မီရွေးပါ။ Credit sale အတွက် customer မဖြစ်မနေလိုသည်။\n4. Received amount နဲ့ change ကိုစစ်ပြီး payment ကိုအတည်ပြုပါ။\n5. Receipt number ကိုသိမ်းထားပြီး Receipts မှာ transaction အောင်မြင်မှုစစ်ပါ။\n\n**အခက်အခဲဖြစ်လျှင်** Stock မလုံလောက်၊ barcode မတွေ့ သို့မဟုတ် checkout ပိတ်ထားပါက product status၊ stock location နဲ့ role permission ကိုစစ်ပါ။""",
        "products": """**လိုအပ်သောအချက်များ** Name, SKU, selling price နဲ့ category; stock tracking သုံးလျှင် cost/initial stock/low-stock threshold ပါဖြည့်ပါ။\n\n**လုပ်ဆောင်ပုံ**\n1. Duplicate SKU/barcode မရှိကြောင်း search လုပ်ပါ။\n2. Add Product မှ required fields ဖြည့်ပြီး Save ပါ။\n3. Product table မှ ပြန်ရှာ၍ price နဲ့ status စစ်ပါ။\n4. Stock correction လိုလျှင် Product quantity ကိုတိုက်ရိုက်မပြင်ဘဲ Inventory Adjustment သုံးပြီး reason မှတ်ပါ။\n\n**သတိပြုရန်** Delete မလုပ်မီ အရောင်းမှတ်တမ်းနဲ့ stock history ရှိ/မရှိစစ်ပါ။ အသုံးမပြုတော့သည့် item ကို inactive ထားခြင်းက history ထိန်းသိမ်းရာတွင် ပိုသင့်တော်ပါတယ်။""",
        "inventory": """**အသေးစိတ် Workflow**\n1. Product နဲ့ warehouse/location မှန်ကန်စွာရွေးပါ။\n2. Stock In/Out quantity၊ reference နဲ့ reason ဖြည့်ပါ။\n3. Save ပြီး Current Stock နဲ့ movement history နှစ်ခုစလုံးစစ်ပါ။\n4. Physical count လုပ်ရာတွင် counted quantity ကိုအရင်မှတ်ပြီး ကွာဟချက်ကို Adjustment ဖြင့်ပြင်ပါ။\n\n**ထိန်းချုပ်မှု** Negative stock၊ low stock နဲ့ expiry records ကိုပုံမှန်စစ်ပါ။ Adjustment လုပ်သူနှင့် reason ကို audit အတွက်ရှင်းလင်းစွာထားပါ။""",
        "receipts": """**Refund Workflow**\n1. Invoice/receipt ကိုရှာပြီး မူရင်း items နဲ့ payment ကိုစစ်ပါ။\n2. Refund လုပ်မည့် item/quantity နဲ့ reason ရွေးပါ။\n3. Refund amount နဲ့ stock ပြန်ဝင်မဝင်ကိုအတည်ပြုပါ။\n4. Save ပြီး refund record၊ customer balance နဲ့ inventory movement ကိုပြန်စစ်ပါ။\n\n**သတိပြုရန်** မှားယွင်းသော invoice ကို refund မလုပ်ရန် date၊ customer နဲ့ total ကိုအရင်တိုက်စစ်ပါ။""",
        "customers": """**အသေးစိတ် Workflow**\n1. ဖုန်းနံပါတ်/အမည်နဲ့ duplicate customer ရှာပါ။\n2. Contact information နဲ့ credit limit/terms ရှိလျှင်ဖြည့်ပါ။\n3. Profile မှ purchase history၊ outstanding balance နဲ့ payments ကိုစစ်ပါ။\n4. အမည်တူ customer များအတွက် ဖုန်းနံပါတ်ကိုအတည်ပြုချက်အဖြစ်သုံးပါ။""",
        "credit": """**Payment စစ်ဆေးပုံ**\n1. Customer outstanding total နဲ့ရွေးထားသော invoice balance ကိုတိုက်စစ်ပါ။\n2. Payment date/method/reference ကိုပြည့်စုံစွာဖြည့်ပါ။\n3. Auto Allocate သုံးပါက အဟောင်းဆုံး invoice မှစတင်ခွဲဝေမှုကို preview စစ်ပါ။\n4. Save ပြီး payment receipt၊ invoice status နဲ့ customer balance တူညီမှုစစ်ပါ။\n\n**မမှန်လျှင်** Amount ကို 0 ထက်ကြီးပြီး outstanding ထက်မကျော်စေရန်စစ်ပါ။ Date format နဲ့ invoice selection ကိုလည်းစစ်ပါ။""",
        "expenses": """**အသေးစိတ် Workflow**\n1. သင့်လျော်သော category ရွေးပြီး expense ဖြစ်ပွားသည့်နေ့ကိုထည့်ပါ။\n2. Amount/payment method/reference ဖြည့်ကာ receipt ရှိလျှင်တွဲပါ။\n3. Save ပြီး date/category filter နဲ့ record ပြန်ရှာပါ။\n4. လစဉ် Reports total နဲ့ expense records ကိုတိုက်စစ်ပါ။\n\n**သတိပြုရန်** Payroll မှအလိုအလျောက်ဖန်တီးသော expense ကိုထပ်မထည့်ပါနှင့်။""",
        "reports": """**တိကျသော Report ရယူပုံ**\n1. Business question နဲ့ကိုက်သည့် report type ရွေးပါ။\n2. Start/End date၊ branch နဲ့ status filters ကိုစစ်ပါ။\n3. On-screen total နဲ့ table row count ကိုကြည့်ပါ။\n4. Export ပြီး file ထဲက date range/total ကိုထပ်စစ်ပါ။\n\n**မှတ်ချက်** Completed/Cancelled/Refunded status ပါဝင်ပုံက report တစ်ခုချင်းမတူနိုင်သောကြောင့် filters ကိုမဖြစ်မနေစစ်ပါ။""",
        "employees": """**ဝန်ထမ်းအသစ်ထည့်သွင်းမှုအစီအစဉ်**\n1. Employee profile နဲ့ photo ဖန်တီးပါ။\n2. လိုအပ်လျှင် POS user account ချိတ်ပါ။\n3. Shift ကို effective date နဲ့ assign ပါ။\n4. ZKTeco User ID သုံးပါက employee mapping ပြုလုပ်ပါ။\n5. Basic salary၊ leave information နဲ့စာရွက်စာတမ်းများဖြည့်ပါ။\n6. Attendance/Performance မှာဝန်ထမ်းပေါ်လာမှုစစ်ပါ။\n\n**ရှာဖွေမှု** Employee ID၊ အမည်၊ department၊ status စသည်ဖြင့် filter လုပ်နိုင်ပြီး AI Chat မှာလည်း အမည်နဲ့မေးနိုင်ပါတယ်။""",
        "attendance": """**နေ့စဉ်လုပ်ငန်းစဉ်**\n1. မှန်ကန်သော date range ရွေးပြီး K20 punches sync လုပ်ပါ။\n2. Employee/issue filters နဲ့ Late, Incomplete, Absent, Half-day, Leave ကိုစစ်ပါ။\n3. Check In Before/After က ထိုနေ့အတွက် effective shift start time ကိုအသုံးပြုပါတယ်။\n4. Missing/မှားယွင်း record ကို reason ပါသော manual correction ဖြင့်ပြင်ပါ။\n5. ပြင်ပြီး status နဲ့ total count ကိုပြန်စစ်ပါ။\n\n**မပေါ်လျှင်** ZKTeco mapping၊ active device၊ assignment effective date နဲ့ရွေးထားသော date range ကိုစစ်ပါ။""",
        "shifts": """**ဥပမာ—08:00 မှ 20:00**\n1. New/Edit Shift မှ Start 08:00, End 20:00 သတ်မှတ်ပါ။\n2. Break နဲ့ late tolerance ရှိလျှင် company policy အတိုင်းဖြည့်ပါ။\n3. Employee ကိုရွေးပြီး Effective From date ဖြင့် Assign ပါ။\n4. Assignment table မှ duplicate/overlap ရှိမရှိစစ်ပါ။\n5. မှားပါက row ရွေးပြီး Edit Assignment သို့ Delete Assignment သုံးပါ။\n\n**သတိပြုရန်** Shift ပြောင်းသည့်နေ့ကို effective date မှန်စွာထားမှ attendance Before/After နဲ့ Late calculation မှန်ပါမယ်။""",
        "leave": """**Request မှ Approval အထိ**\n1. Employee၊ leave type နဲ့ start/end date ရွေးပါ။\n2. Reason/attachment လိုအပ်လျှင်ထည့်ပြီး Pending အဖြစ်သိမ်းပါ။\n3. Manager/Admin က overlap၊ balance နဲ့ attendance ကိုစစ်ပါ။\n4. Approve/Reject လုပ်ပြီး status ပြန်စစ်ပါ။\n5. Approved period ကို Attendance tab မှ Leave အဖြစ်ပေါ်လာမှုစစ်ပါ။""",
        "payroll": """**လစဉ် Payroll Workflow**\n1. Employee profile ရဲ့ basic salary နဲ့ active status ကိုစစ်ပါ။\n2. Month ရွေးပြီး attendance၊ overtime၊ leave၊ advances/deductions ပြည့်စုံကြောင်းစစ်ပါ။\n3. Create Payroll လုပ်ပြီး gross၊ deductions နဲ့ net တစ်ခုချင်းစစ်ပါ။\n4. Draft အဆင့်မှာမှားသည်များကိုပြင်ပါ။\n5. ငွေပေးချေပြီးမှ Mark Paid လုပ်ကာ payment date/method ကိုမှတ်ပါ။\n6. Salary expense တစ်ခုပဲဖန်တီးထားကြောင်း Expenses မှာစစ်ပါ။\n\n**သတိပြုရန်** Paid payroll ကိုပြန်ပြင်မီ accounting impact နဲ့ expense record ကိုစစ်ပါ။""",
        "documents": """**လုပ်ဆောင်ပုံ**\n1. Employee နဲ့ document type ရွေးပါ။\n2. Document number၊ issue/expiry date နဲ့ notes ဖြည့်ပါ။\n3. File တွဲပြီး Save ကာ search ဖြင့်ပြန်ရှာပါ။\n4. Expiring/Expired filter နဲ့ သက်တမ်းကုန်မည့်စာရွက်စာတမ်းများကိုပုံမှန်စစ်ပါ။\n\n**ဖိုင်ထိန်းသိမ်းမှု** App က path ကိုသာသိမ်းသည့် configuration ဖြစ်လျှင် မူရင်းဖိုင်ကိုမရွှေ့ဘဲ backup ထားပါ။""",
        "commission": """**Advance**: Amount/date/reason ထည့် → outstanding စစ် → repayment တိုင်း record တင် → လက်ကျန်ပြန်စစ်ပါ။\n\n**Commission**: Rule ရဲ့ rate/target/effective period သတ်မှတ် → employee sales link စစ် → Performance date range ရွေး → calculated commission စစ်ပါ။\n\n**သတိပြုရန်** Advance ကို payroll deduction အဖြစ်ယူမည်ဆိုလျှင် နှစ်ခါမနုတ်မိစေရန် payroll record နဲ့ repayment ကိုတိုက်စစ်ပါ။""",
        "performance": """**တိကျစေရန်**\n1. Employee profile ကိုမှန်ကန်သော POS user နဲ့ချိတ်ပါ။\n2. Date range/branch/employee filters ရွေးပါ။\n3. Sales count၊ revenue၊ refunds နဲ့ discounts ကို Receipts/Reports နှင့်တိုက်စစ်ပါ။\n4. Target/rate ကိုစစ်ပြီး commission result ကိုအတည်ပြုပါ။\n\nဝန်ထမ်းအမည်နဲ့ `ဖိုးသား performance ဒီလ` ကဲ့သို့ AI Chat မှာမေးနိုင်ပါတယ်။""",
        "cash_sessions": """**နေ့စဉ် Workflow**\n1. အရောင်းမစမီ Opening Cash ကိုရေတွက်ပြီး Open Session လုပ်ပါ။\n2. Session အတွင်း cash transactions ကိုတူညီသော cashier account ဖြင့်လုပ်ပါ။\n3. ပိတ်ချိန် drawer cash ကိုရေတွက်ပြီး Actual Cash ဖြည့်ပါ။\n4. Expected နဲ့ Difference ကိုစစ်၍ ကွာဟချက်ရှိလျှင် note/reason မှတ်ပါ။\n5. Close Session လုပ်ပြီး report/record ကိုသိမ်းပါ။\n\n**မပိတ်နိုင်လျှင်** Open session row မှန်ကန်မှု၊ employee mapping နဲ့ permission ကိုစစ်ပါ။""",
        "ai": """**မေးခွန်းရေးနည်း** Module + အမည်/ကာလ + လိုချင်သောအချက်ကိုရေးပါ။ ဥပမာ `ဖိုးသား attendance 2026-08-01 to 2026-08-17`, `low stock list`, `ဒီနေ့ sales summary`။\n\nအသုံးပြုနည်းအတွက် `Attendance အသုံးပြုပုံ`၊ လက်ရှိ data အတွက် `EMP-0008 attendance ဒီလ` လို့ခွဲမေးပါ။ AI အဖြေကိုအရေးကြီးသော accounting/HR ဆုံးဖြတ်ချက်မလုပ်မီ မူရင်း table/report နှင့်တိုက်စစ်ပါ။""",
        "users": """**Account Setup**\n1. Unique username နဲ့ခိုင်မာသော password သတ်မှတ်ပါ။\n2. အလုပ်တာဝန်နှင့်ကိုက်သော role ရွေးပါ။\n3. Employee ဖြစ်လျှင် profile ထဲက POS account link ချိတ်ပါ။\n4. Login စမ်းပြီးလိုအပ်သော pages သာမြင်ရကြောင်းစစ်ပါ။\n5. အလုပ်ထွက်သူ account ကို history မပျက်စေရန် delete ထက် disable လုပ်ပါ။""",
        "permissions": """**အကြံပြုသတ်မှတ်ချက်** Admin ကိုအနည်းဆုံးထားပါ။ Manager ကို operations/HR manage၊ Cashier ကို sales နှင့်လိုအပ်သော AI access၊ Viewer ကို read-only ပေးပါ။\n\n**စစ်ဆေးပုံ**\n1. Role ကိုရွေးပြီး page-level View/Manage permissions စစ်ပါ။\n2. Save ပြီး test user နဲ့ login ပြန်ဝင်ပါ။\n3. Page မြင်နိုင်မှုသာမက Add/Edit/Delete/Export buttons ကိုပါစမ်းပါ။\n4. Access Denied ဖြစ်ပါက user role၊ permission key နဲ့ session refresh ကိုစစ်ပါ။""",
        "settings": """**ZKTeco K20 Setup**\n1. Settings > ZKTeco Devices မှ Device ID, IP, Port, Comm Key ဖြည့်ပါ။\n2. Active ဖွင့်ပြီး connection test/sync လုပ်ပါ။\n3. Device User ID ကို Employee ID နဲ့ mapping ချိတ်ပါ။\n4. Punches sync ပြီး Attendance မှာ date/employee ဖြင့်စစ်ပါ။\n\nသင့်စက်အတွက် Device ID 1, IP 192.168.110.245, Port 4370, Comm Key 0 ဖြစ်ပြီး PC နဲ့ device တူညီသော network ထဲရှိရန်လိုပါတယ်။ Configuration ပြောင်းပြီးနောက် connection စမ်းသပ်ပါ။""",
        "backup": """**လုံခြုံသောလုပ်ဆောင်စဉ်**\n1. Backup မလုပ်မီ active sales/transactions ပြီးဆုံးမှုစစ်ပါ။\n2. Backup ဖန်တီးပြီး filename/date/size နဲ့သိမ်းရာနေရာကိုစစ်ပါ။\n3. Copy တစ်ခုကိုအခြား drive/location မှာထားပါ။\n4. Restore မလုပ်မီ လက်ရှိ database ကိုနောက်ထပ် backup ယူပါ။\n5. Restore ပြီး login၊ products၊ sales နဲ့ reports အနည်းငယ်စမ်းစစ်ပါ။\n\nFactory Reset သည်ပြန်မရနိုင်သော data loss ဖြစ်နိုင်သောကြောင့် verified backup မရှိဘဲမလုပ်သင့်ပါ။""",
    }

    @classmethod
    def handles(cls, query):
        text=(query or "").lower()
        return any(word in text for word in cls.HELP_WORDS)

    @classmethod
    def handle(cls, query):
        if not cls.handles(query):return None
        text=(query or "").lower()
        for topic,words in cls.TOPICS:
            if any(word in text for word in words):
                guide = cls.GUIDES[topic]
                detail = cls.DETAILS.get(topic)
                if detail:
                    guide = f"{guide}\n\n---\n\n{detail}\n\n**ဆက်မေးနိုင်သောပုံစံ**\n`{topic} အသုံးပြုပုံကို အဆင့်လိုက်ရှင်းပြပါ` သို့မဟုတ် ပြဿနာဖြစ်နေသည့်အဆင့်ကို တိတိကျကျရေးပါ။"
                return cls._result(guide)
        return cls._result(cls._overview())

    @staticmethod
    def _result(message):return {"type":"usage_guide","data":[],"message":message,"sql":""}

    @classmethod
    def _overview(cls):
        return """📘 **ZAY POS Project User Guide**

အောက်ပါ module တစ်ခုချင်းစီကို `အသုံးပြုပုံ` သို့မဟုတ် `how to use` နဲ့မေးနိုင်ပါတယ်—

• Sales / Checkout
• Products & Inventory
• Receipts & Refunds
• Customers & Credit Payments
• Expenses & Reports
• Employees, Attendance, Shifts, Leave
• Payroll, Documents, Advances & Commission
• Performance & Cash Sessions
• AI Pages
• Users, Roles & Permissions
• Settings, ZKTeco, Backup & Restore

**Examples:**
• `Sales အသုံးပြုပုံ`
• `credit payment ဘယ်လိုလုပ်မလဲ`
• `Payroll how to use`
• `ZKTeco setting လမ်းညွှန်`
• `backup restore အသုံးပြုပုံ`"""
