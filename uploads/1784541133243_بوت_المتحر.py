import asyncio
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import warnings
from uuid import uuid4

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, NetworkError
from telegram.warnings import PTBUserWarning
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
warnings.filterwarnings("ignore", category=PTBUserWarning, message="If 'per_message=False'.*")

LOGGER = logging.getLogger(__name__)
ENV_FILE = ".env"
TOKEN_ENV_NAME = "TELEGRAM_BOT_TOKEN"
ADMIN_IDS_ENV_NAME = "ADMIN_IDS"
TAP_SECRET_KEY_ENV_NAME = "TAP_SECRET_KEY"
TAP_CURRENCY_ENV_NAME = "TAP_CURRENCY"
TAP_SOURCE_ID_ENV_NAME = "TAP_SOURCE_ID"
TAP_REDIRECT_URL_ENV_NAME = "TAP_REDIRECT_URL"
TAP_POST_URL_ENV_NAME = "TAP_POST_URL"
TAP_CUSTOMER_EMAIL_ENV_NAME = "TAP_CUSTOMER_EMAIL"
TAP_CUSTOMER_PHONE_COUNTRY_CODE_ENV_NAME = "TAP_CUSTOMER_PHONE_COUNTRY_CODE"
TAP_CUSTOMER_PHONE_NUMBER_ENV_NAME = "TAP_CUSTOMER_PHONE_NUMBER"
NOWPAYMENTS_API_KEY_ENV_NAME = "NOWPAYMENTS_API_KEY"
NOWPAYMENTS_JWT_TOKEN_ENV_NAME = "NOWPAYMENTS_JWT_TOKEN"
NOWPAYMENTS_EMAIL_ENV_NAME = "NOWPAYMENTS_EMAIL"
NOWPAYMENTS_PASSWORD_ENV_NAME = "NOWPAYMENTS_PASSWORD"
NOWPAYMENTS_PRICE_CURRENCY_ENV_NAME = "NOWPAYMENTS_PRICE_CURRENCY"
NOWPAYMENTS_SUCCESS_URL_ENV_NAME = "NOWPAYMENTS_SUCCESS_URL"
NOWPAYMENTS_CANCEL_URL_ENV_NAME = "NOWPAYMENTS_CANCEL_URL"
TOPUP_CREDIT_RATE_ENV_NAME = "TOPUP_CREDIT_RATE"
PRODUCTS_FILE = "products.json"
USERS_FILE = "users.json"
USERNAMES_FILE = "usernames.json"
BOT_USERS_FILE = "bot_users.json"
USER_OPERATIONS_FILE = "user_operations.json"
ARCHIVE_FILE = "archive.json"
EMPLOYEES_FILE = "employees.json"
STAFF_OPERATIONS_FILE = "staff_operations.json"
TOPUPS_FILE = "topups.json"
SUPPORT_TICKETS_FILE = "support_tickets.json"
BOT_SETTINGS_FILE = "bot_settings.json"
PRODUCT_NAME, PRODUCT_DESCRIPTION, PRODUCT_PRICE, DELIVERY_CONTENT = range(4)
USERNAME_CATEGORY_NAME, USERNAME_NAME, USERNAME_PRICE, USERNAME_DELIVERY = range(4, 8)
EMPLOYEE_ID = 8
TOPUP_AMOUNT = 9
SUPPORT_MESSAGE = 10
SUPPORT_REPLY_MESSAGE = 11
REQUIRED_CHANNEL = 12
TOPUP_PAYMENT_ID = 13
BROADCAST_MESSAGE = 14
DELETE_USER_INPUT = 15
PAYMENT_SETTING_INPUT = 16
NOWPAYMENTS_API_BASE = "https://api.nowpayments.io/v1"
TAP_API_BASE = "https://api.tap.company/v2"
NOWPAYMENTS_JWT_CACHE = {"token": "", "expires_at": 0}
TOPUP_LINK_TTL_SECONDS = 20 * 60
USERNAME_REPURCHASE_BLOCK_SECONDS = 24 * 60 * 60
USERNAME_ABUSE_WINDOW_SECONDS = 10 * 60
USERNAME_ABUSE_ATTEMPT_LIMIT = 3
RESERVATION_SECONDS = 24 * 60 * 60
RESERVATION_CANCEL_SECONDS = 60 * 60
RESERVATION_RECANCEL_BLOCK_SECONDS = 2 * 24 * 60 * 60
SHORT_ID_LENGTH = 10
PURCHASES_PAGE_SIZE = 5


WELCOME_MESSAGE = (
    """🎉 مرحبًا بك في TikTok STORE!

أهلًا بك! نحن سعداء بوجودك معنا. 🤍
هنا ستجد مجموعة متنوعة من المنتجات والخدمات، مع تجربة شراء سهلة وآمنة.

إذا احتجت أي مساعدة أو كان لديك أي استفسار، فلا تتردد في التواصل معنا، وسنكون سعداء بخدمتك.

استخدم الأزرار أدناه للبدء واستمتع بتجربة تسوق مميزة! 🚀"""
)


def rtl_text(text: str) -> str:
    return f"\u200f{text}\u200f"


def main_menu_keyboard(show_admin: bool = False, show_employee: bool = False) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📦 المنتجات الرقمية", callback_data="digital_products"),
            InlineKeyboardButton("🔤 قسم اليوزرات", callback_data="usernames"),
        ],
        [InlineKeyboardButton("🧾 العمليات", callback_data="operations")],
        [InlineKeyboardButton("💬 المساعدة و الدعم", callback_data="support")],
    ]

    if show_admin:
        keyboard.append([InlineKeyboardButton("🛠️ لوحة الادمن", callback_data="admin_menu")])
    elif show_employee:
        keyboard.append([InlineKeyboardButton("👨‍💼 لوحة الموظف", callback_data="employee_menu")])

    return InlineKeyboardMarkup(keyboard)


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🏠 العودة للقائمة الرئيسية", callback_data="main_menu")]]
    )


def wallet_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ إضافة أموال", callback_data="add_wallet_funds")],
            [InlineKeyboardButton("🏠 العودة للقائمة الرئيسية", callback_data="main_menu")],
        ]
    )


def topup_methods_keyboard() -> InlineKeyboardMarkup:
    keyboard = []
    if is_nowpayments_enabled():
        keyboard.append([InlineKeyboardButton("💳 الدفع عبر NOWPayments", callback_data="topup_method:nowpayments")])
    if is_tap_enabled():
        keyboard.append([InlineKeyboardButton("💸 البطاقة / Apple Pay", callback_data="topup_method:tap")])
    keyboard.append([InlineKeyboardButton("↩️ رجوع للمحفظة", callback_data="wallet")])
    return InlineKeyboardMarkup(keyboard)


def topup_invoice_keyboard(invoice_url: str, label: str = "🌐 فتح رابط الدفع") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(label, url=invoice_url)],
            [InlineKeyboardButton("🏠 العودة للقائمة الرئيسية", callback_data="main_menu")],
        ]
    )


def topup_payment_keyboard(payment_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔄 تحقق من الدفع", callback_data=f"check_topup:{payment_id}")],
            [InlineKeyboardButton("↩️ رجوع للمحفظة", callback_data="wallet")],
        ]
    )


def direct_payment_keyboard(invoice_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💳 ادفع الآن", url=invoice_url)],
            [InlineKeyboardButton("🏠 العودة للقائمة الرئيسية", callback_data="main_menu")],
        ]
    )


SUPPORT_CATEGORIES = {
    "payment": "💳 مشكلة دفع / شحن",
    "product": "📦 مشكلة منتج",
    "username": "🔤 مشكلة يوزر",
    "order": "🛒 مشكلة طلب",
    "other": "💬 استفسار آخر",
}


def support_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(label, callback_data=f"support_new:{key}")]
            for key, label in SUPPORT_CATEGORIES.items()
        ]
        + [
            [InlineKeyboardButton("🎫 تذاكري", callback_data="support_my_tickets")],
            [InlineKeyboardButton("🏠 العودة للقائمة الرئيسية", callback_data="main_menu")],
        ]
    )


def support_collect_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ إنشاء التذكرة", callback_data="support_finish_ticket")],
            [InlineKeyboardButton("❌ الغاء", callback_data="support_cancel_ticket")],
        ]
    )


def user_tickets_keyboard(user_id: int) -> InlineKeyboardMarkup:
    tickets = get_user_tickets(user_id)
    keyboard = []
    for ticket in reversed(tickets[-10:]):
        status = "✅" if ticket.get("status") == "closed" else "⏳"
        keyboard.append(
            [
                InlineKeyboardButton(
                    rtl_text(f"{status} {ticket.get('number', ticket.get('id'))} - {ticket.get('category_label', 'دعم')}"),
                    callback_data=f"support_ticket:{ticket['id']}",
                )
            ]
        )

    keyboard.append([InlineKeyboardButton("↩️ رجوع للدعم", callback_data="support")])
    keyboard.append([InlineKeyboardButton("🏠 العودة للقائمة الرئيسية", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def user_ticket_keyboard(ticket: dict) -> InlineKeyboardMarkup:
    keyboard = []
    if ticket.get("status") != "closed":
        keyboard.append([InlineKeyboardButton("➕ إضافة رد", callback_data=f"support_add:{ticket['id']}")])
    keyboard.append([InlineKeyboardButton("↩️ رجوع لتذاكري", callback_data="support_my_tickets")])
    keyboard.append([InlineKeyboardButton("🏠 العودة للقائمة الرئيسية", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def staff_tickets_keyboard() -> InlineKeyboardMarkup:
    tickets = get_staff_visible_tickets()
    keyboard = []
    for ticket in tickets[:20]:
        status = "✅" if ticket.get("status") == "closed" else "⏳"
        keyboard.append(
            [
                InlineKeyboardButton(
                    rtl_text(f"{status} {ticket.get('number', ticket.get('id'))} - {ticket.get('category_label', 'دعم')}"),
                    callback_data=f"staff_ticket:{ticket['id']}",
                )
            ]
        )

    keyboard.append([InlineKeyboardButton("↩️ رجوع", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def staff_ticket_keyboard(ticket: dict) -> InlineKeyboardMarkup:
    keyboard = []
    if ticket.get("status") != "closed":
        keyboard.append([InlineKeyboardButton("✍️ رد على التذكرة", callback_data=f"staff_ticket_reply:{ticket['id']}")])
        keyboard.append([InlineKeyboardButton("🔒 اغلاق التذكرة", callback_data=f"staff_ticket_close:{ticket['id']}")])
    keyboard.append([InlineKeyboardButton("↩️ رجوع للتذاكر", callback_data="staff_tickets")])
    return InlineKeyboardMarkup(keyboard)


def products_keyboard(products: list[dict]) -> InlineKeyboardMarkup:
    keyboard = []
    for product in products:
        quantity = len(get_delivery_items(product))
        product_name = product.get("name", "منتج بدون اسم")
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"📦 {product_name} - المتوفر: {quantity}",
                    callback_data=f"product:{product['id']}",
                )
            ]
        )

    keyboard.append([InlineKeyboardButton("🏠 العودة للقائمة الرئيسية", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def product_purchase_keyboard(product_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🛒 شراء المنتج", callback_data=f"buy:{product_id}")],
            [InlineKeyboardButton("↩️ رجوع للمنتجات", callback_data="digital_products")],
        ]
    )


def back_to_products_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("↩️ رجوع للمنتجات", callback_data="digital_products")]]
    )


def back_to_username_categories_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("↩️ رجوع للاقسام", callback_data="usernames")]]
    )


def back_to_admin_products_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("↩️ رجوع للمنتجات", callback_data="admin_show_products")]]
    )


def back_to_admin_username_categories_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("↩️ رجوع للاقسام", callback_data="admin_username_categories")]]
    )


def back_to_admin_usernames_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("↩️ رجوع لقسم اليوزرات", callback_data="admin_usernames")]]
    )


def back_to_admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("↩️ رجوع للوحة الادمن", callback_data="admin_menu")]]
    )


def admin_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🗑️ تصفير إحصائيات المبيعات", callback_data="admin_reset_sales_stats")],
            [InlineKeyboardButton("↩️ رجوع للوحة الادمن", callback_data="admin_menu")],
        ]
    )


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📊 إحصائيات المتجر", callback_data="admin_stats")],
            [InlineKeyboardButton("➕ اضافة المنتجات", callback_data="admin_add_product")],
            [InlineKeyboardButton("📋 عرض المنتجات", callback_data="admin_show_products")],
            [InlineKeyboardButton("🔤 قسم اليوزرات", callback_data="admin_usernames")],
            [InlineKeyboardButton("⚙️ إعدادات طرق الدفع", callback_data="admin_payment_settings")],
            [InlineKeyboardButton("🎫 تذاكر الدعم", callback_data="staff_tickets")],
            [InlineKeyboardButton("👨‍💼 إدارة الموظفين", callback_data="admin_employees")],
            [InlineKeyboardButton("📢 الاشتراك الاجباري", callback_data="admin_required_channel")],
            [InlineKeyboardButton("📢 إرسال إذاعة", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🏠 العودة للقائمة الرئيسية", callback_data="main_menu")],
        ]
    )


def required_channel_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✏️ تحديد القناة", callback_data="admin_set_required_channel")],
            [InlineKeyboardButton("🗑️ تعطيل الاشتراك الاجباري", callback_data="admin_clear_required_channel")],
            [InlineKeyboardButton("↩️ رجوع للوحة الادمن", callback_data="admin_menu")],
        ]
    )


def required_channel_join_keyboard(channel: dict) -> InlineKeyboardMarkup:
    keyboard = []
    url = get_required_channel_url(channel)
    if url:
        keyboard.append([InlineKeyboardButton("📢 الاشتراك في القناة", url=url)])
    keyboard.append([InlineKeyboardButton("✅ تحققت من الاشتراك", callback_data="check_required_channel")])
    return InlineKeyboardMarkup(keyboard)


def admin_employees_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ توظيف موظف", callback_data="admin_add_employee")],
            [InlineKeyboardButton("📋 عرض الموظفين", callback_data="admin_show_employees")],
            [InlineKeyboardButton("↩️ رجوع للوحة الادمن", callback_data="admin_menu")],
        ]
    )


def employee_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📥 اضافة مخزون المنتجات الرقمية", callback_data="employee_products")],
            [InlineKeyboardButton("🔤 اضافة يوزر داخل قسم", callback_data="employee_username_categories")],
            [InlineKeyboardButton("🎫 تذاكر الدعم", callback_data="staff_tickets")],
            [InlineKeyboardButton("🏠 العودة للقائمة الرئيسية", callback_data="main_menu")],
        ]
    )


def admin_usernames_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🗂️ اضافة قسم جديد", callback_data="admin_add_username_category")],
            [InlineKeyboardButton("📁 اختيار قسم", callback_data="admin_username_categories")],
            [InlineKeyboardButton("⏳ الحجوزات", callback_data="admin_username_reservations")],
            [InlineKeyboardButton("↩️ رجوع للوحة الادمن", callback_data="admin_menu")],
        ]
    )


def username_categories_keyboard(categories: list[dict], prefix: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(f"📁 {category.get('name', 'قسم بدون اسم')}", callback_data=f"{prefix}:{category['id']}")]
        for category in categories
    ]
    keyboard.append([InlineKeyboardButton("↩️ رجوع", callback_data="admin_usernames" if prefix.startswith("admin") else "main_menu")])
    return InlineKeyboardMarkup(keyboard)


def admin_username_category_keyboard(category_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 عرض اليوزرات", callback_data=f"admin_show_usernames:{category_id}")],
            [InlineKeyboardButton("➕ اضافة يوزر جديد", callback_data=f"admin_add_username:{category_id}")],
            [InlineKeyboardButton("🗑️ حذف القسم", callback_data=f"admin_delete_username_category:{category_id}")],
            [InlineKeyboardButton("↩️ رجوع للاقسام", callback_data="admin_username_categories")],
        ]
    )


def admin_usernames_items_keyboard(category: dict) -> InlineKeyboardMarkup:
    keyboard = []
    for item in category.get("items", []):
        status = item.get("status", "available")
        status_icon = "🟢" if status == "available" else "🟡"
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"{status_icon} {item.get('name', 'يوزر بدون اسم')} - {format_price(get_username_price(item))} ريال",
                    callback_data=f"admin_username_item:{category['id']}:{item['id']}",
                )
            ]
        )

    keyboard.append([InlineKeyboardButton("↩️ رجوع للقسم", callback_data=f"admin_username_category:{category['id']}")])
    return InlineKeyboardMarkup(keyboard)


def admin_username_item_details_keyboard(category_id: str, item_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🗑️ حذف اليوزر", callback_data=f"admin_delete_username_item:{category_id}:{item_id}")],
            [InlineKeyboardButton("↩️ رجوع لليوزرات", callback_data=f"admin_show_usernames:{category_id}")],
        ]
    )


def usernames_items_keyboard(category: dict) -> InlineKeyboardMarkup:
    keyboard = []
    for item in category.get("items", []):
        if item.get("status", "available") != "available":
            continue
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"🔤 {item.get('name', 'يوزر بدون اسم')} - {format_price(get_username_price(item))} ريال",
                    callback_data=f"username_item:{category['id']}:{item['id']}",
                )
            ]
        )

    keyboard.append([InlineKeyboardButton("↩️ رجوع للاقسام", callback_data="usernames")])
    return InlineKeyboardMarkup(keyboard)


def username_purchase_keyboard(category_id: str, item_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🛒 شراء", callback_data=f"buy_username:{category_id}:{item_id}")],
            [InlineKeyboardButton("↩️ رجوع", callback_data=f"username_category:{category_id}")],
        ]
    )


def username_reserved_keyboard(category_id: str, item_id: str, can_cancel: bool = True) -> InlineKeyboardMarkup:
    keyboard = []
    keyboard.append([InlineKeyboardButton("🛒 شراء", callback_data=f"buy_reserved_username:{category_id}:{item_id}")])
    if can_cancel:
        keyboard.append([InlineKeyboardButton("❌ الغاء الحجز", callback_data=f"cancel_username_reservation:{category_id}:{item_id}")])
    keyboard.append([InlineKeyboardButton("🧾 العمليات", callback_data="operations")])
    keyboard.append([InlineKeyboardButton("↩️ رجوع", callback_data=f"username_category:{category_id}")])
    return InlineKeyboardMarkup(keyboard)


def operations_keyboard(user_id: int, view: str = "all") -> InlineKeyboardMarkup:
    keyboard = []
    if view != "reservations":
        keyboard.append([InlineKeyboardButton("🛒 المشتريات", callback_data="operations:purchases")])
    reservation = get_active_user_reservation(user_id)
    if view == "reservations" and reservation:
        category_id, item_id, item = reservation
        can_cancel = can_cancel_reservation(item.get("reservation", {}))
        keyboard.append(
            [InlineKeyboardButton("🛒 شراء الحجز الحالي", callback_data=f"buy_reserved_username:{category_id}:{item_id}")]
        )
        if can_cancel:
            keyboard.append(
                [InlineKeyboardButton("❌ الغاء الحجز الحالي", callback_data=f"cancel_username_reservation:{category_id}:{item_id}")]
            )

    if view == "reservations":
        keyboard.append([InlineKeyboardButton(rtl_text("↩️ رجوع للعمليات"), callback_data="operations:all")])

    keyboard.append([InlineKeyboardButton("🏠 العودة للقائمة الرئيسية", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def purchases_keyboard(user_id: int, page: int = 0) -> InlineKeyboardMarkup:
    purchases = list(reversed(get_user_purchase_operations(user_id)))
    total_pages = max(1, (len(purchases) + PURCHASES_PAGE_SIZE - 1) // PURCHASES_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    page_purchases = purchases[page * PURCHASES_PAGE_SIZE : (page + 1) * PURCHASES_PAGE_SIZE]
    keyboard = []
    for operation in page_purchases:
        item_name = operation.get("item_name", "منتج بدون اسم")
        keyboard.append(
            [
                InlineKeyboardButton(
                    rtl_text(f"📋 {item_name}"),
                    callback_data=f"operation_purchase:{operation['id']}",
                )
            ]
        )

    if total_pages > 1:
        navigation = []
        if page > 0:
            navigation.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"operations:purchases:{page - 1}"))
        if page < total_pages - 1:
            navigation.append(InlineKeyboardButton("التالي ➡️", callback_data=f"operations:purchases:{page + 1}"))
        if navigation:
            keyboard.append(navigation)

    keyboard.append([InlineKeyboardButton(rtl_text("↩️ رجوع للعمليات"), callback_data="operations:all")])
    keyboard.append([InlineKeyboardButton(rtl_text("🏠 العودة للقائمة الرئيسية"), callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def product_flow_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("❌ الغاء اضافة المنتج", callback_data="cancel_add_product")],
        ]
    )


def delivery_flow_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏹️ التوقف عن اضافه التسليم", callback_data="stop_delivery")],
        ]
    )


def products_admin_keyboard(products: list[dict]) -> InlineKeyboardMarkup:
    keyboard = []
    for product in products:
        product_name = product.get("name", "منتج بدون اسم")
        keyboard.append(
            [InlineKeyboardButton(f"📦 {product_name}", callback_data=f"admin_product:{product['id']}")]
        )

    keyboard.append([InlineKeyboardButton("↩️ رجوع للوحة الادمن", callback_data="admin_menu")])
    return InlineKeyboardMarkup(keyboard)


def employee_products_keyboard(products: list[dict]) -> InlineKeyboardMarkup:
    keyboard = []
    for product in products:
        product_name = product.get("name", "منتج بدون اسم")
        keyboard.append(
            [InlineKeyboardButton(f"📦 {product_name}", callback_data=f"employee_delivery:{product['id']}")]
        )

    keyboard.append([InlineKeyboardButton("↩️ رجوع للوحة الموظف", callback_data="employee_menu")])
    return InlineKeyboardMarkup(keyboard)


def employee_username_categories_keyboard(categories: list[dict]) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(f"📁 {category.get('name', 'قسم بدون اسم')}", callback_data=f"employee_username_category:{category['id']}")]
        for category in categories
    ]
    keyboard.append([InlineKeyboardButton("↩️ رجوع للوحة الموظف", callback_data="employee_menu")])
    return InlineKeyboardMarkup(keyboard)


def employee_username_category_keyboard(category_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ اضافة يوزر جديد", callback_data=f"employee_add_username:{category_id}")],
            [InlineKeyboardButton("↩️ رجوع للاقسام", callback_data="employee_username_categories")],
        ]
    )


def product_admin_keyboard(product_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📥 اضافة مخزون التسليم التلقائي",
                    callback_data=f"admin_delivery:{product_id}",
                )
            ],
            [InlineKeyboardButton("🗑️ حذف المنتج", callback_data=f"admin_delete_product:{product_id}")],
            [InlineKeyboardButton("↩️ رجوع للمنتجات", callback_data="admin_show_products")],
        ]
    )


def load_env_file(path: str = ENV_FILE) -> None:
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def ensure_env_file_created(token: str, admin_ids: str) -> None:
    if not os.path.exists(ENV_FILE):
        default_env_content = f"""TELEGRAM_BOT_TOKEN={token}
ADMIN_IDS={admin_ids}
TAP_SECRET_KEY=
TAP_CURRENCY=SAR
TAP_SOURCE_ID=src_all
TAP_REDIRECT_URL=https://example.com
TAP_POST_URL=
TAP_CUSTOMER_EMAIL=
TAP_CUSTOMER_PHONE_COUNTRY_CODE=
TAP_CUSTOMER_PHONE_NUMBER=
NOWPAYMENTS_API_KEY=
NOWPAYMENTS_JWT_TOKEN=
NOWPAYMENTS_PRICE_CURRENCY=usd
TOPUP_CREDIT_RATE=1
NOWPAYMENTS_SUCCESS_URL=
NOWPAYMENTS_CANCEL_URL=
NOWPAYMENTS_EMAIL=
NOWPAYMENTS_PASSWORD=
"""
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write(default_env_content)
    else:
        update_env_file_key(TOKEN_ENV_NAME, token)
        update_env_file_key(ADMIN_IDS_ENV_NAME, admin_ids)


def setup_initial_env_if_missing() -> None:
    load_env_file()

    token = os.getenv(TOKEN_ENV_NAME, "").strip()
    admin_ids = os.getenv(ADMIN_IDS_ENV_NAME, "").strip()

    if not token or not admin_ids:
        print("\n==================================================")
        print("⚙️  إعداد البوت لأول مرة / First-Time Setup")
        print("==================================================")
        print("لم يتم العثور على التوكن أو آيدي الآدمن.")

        if not token:
            while not token:
                token = input("🤖 أدخل توكن البوت (TELEGRAM_BOT_TOKEN): ").strip()
                if not token:
                    print("❌ التوكن مطلوب لتشغيل البوت.")

        if not admin_ids:
            while not admin_ids:
                admin_ids = input("👨‍💼 أدخل آيدي الآدمن (ADMIN_IDS): ").strip()
                if not admin_ids:
                    print("❌ آيدي الآدمن مطلوب لتشغيل البوت.")

        ensure_env_file_created(token, admin_ids)
        os.environ[TOKEN_ENV_NAME] = token
        os.environ[ADMIN_IDS_ENV_NAME] = admin_ids
        print("✅ تم إنشاء وتحديث ملف .env بنجاح!\n")


def get_admin_ids() -> set[int]:
    raw_admin_ids = os.getenv(ADMIN_IDS_ENV_NAME, "")
    admin_ids = set()

    for raw_admin_id in raw_admin_ids.split(","):
        raw_admin_id = raw_admin_id.strip()
        if not raw_admin_id:
            continue

        try:
            admin_ids.add(int(raw_admin_id))
        except ValueError:
            LOGGER.warning("Invalid admin id in %s: %s", ADMIN_IDS_ENV_NAME, raw_admin_id)

    return admin_ids


def get_staff_ids() -> set[int]:
    staff_ids = set(get_admin_ids())
    for employee in load_employees().get("employees", []):
        employee_id = employee.get("id")
        if not employee_id:
            continue
        try:
            staff_ids.add(int(employee_id))
        except (TypeError, ValueError):
            LOGGER.warning("Invalid employee id in %s: %s", EMPLOYEES_FILE, employee_id)
    return staff_ids


def is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and user.id in get_admin_ids())


def is_employee(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return False
    return any(
        employee.get("id") == user.id
        for employee in load_employees().get("employees", [])
    )


def can_manage_stock(update: Update) -> bool:
    return is_admin(update) or is_employee(update)


def can_manage_usernames(update: Update) -> bool:
    return is_admin(update) or is_employee(update)


def get_actor_info(user, role: str) -> dict:
    return {
        "role": role,
        "id": user.id if user else None,
        "name": get_user_display_name(user),
        "username": user.username if user and user.username else "",
    }


def log_staff_operation(user, role: str, action: str, target: dict) -> None:
    data = load_staff_operations()
    data["operations"].append(
        {
            "id": make_short_id(),
            "action": action,
            "actor": get_actor_info(user, role),
            "target": target,
            "created_at": int(time.time()),
        }
    )
    save_staff_operations(data)


def get_known_user_info(user_id: int) -> dict:
    data = load_bot_users()
    entry = find_bot_user_entry(data, user_id)
    if not entry:
        return {"name": "غير معروف", "username": ""}
    return {
        "name": entry.get("name", "غير معروف"),
        "username": entry.get("username", ""),
    }


def employee_display_name(employee: dict) -> str:
    name = employee.get("name")
    username = employee.get("username")
    user_id = employee.get("id")

    if name and username:
        return f"{name} (@{username})"
    if name:
        return name
    if username:
        return f"@{username}"
    return str(user_id)


def employees_keyboard() -> InlineKeyboardMarkup:
    data = load_employees()
    keyboard = []
    for employee in data.get("employees", []):
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"👨‍💼 {employee_display_name(employee)}",
                    callback_data=f"admin_employee:{employee['id']}",
                )
            ]
        )

    keyboard.append([InlineKeyboardButton("↩️ رجوع لإدارة الموظفين", callback_data="admin_employees")])
    return InlineKeyboardMarkup(keyboard)


def employee_details_keyboard(employee_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🗑️ حذف الموظف", callback_data=f"admin_delete_employee:{employee_id}")],
            [InlineKeyboardButton("↩️ رجوع للموظفين", callback_data="admin_show_employees")],
        ]
    )


def get_employee(employee_id: int) -> dict | None:
    for employee in load_employees().get("employees", []):
        if employee.get("id") == employee_id:
            return employee
    return None


def delete_employee(employee_id: int) -> dict | None:
    data = load_employees()
    for index, employee in enumerate(data.get("employees", [])):
        if employee.get("id") == employee_id:
            deleted_employee = data["employees"].pop(index)
            save_employees(data)
            return deleted_employee
    return None


def get_employee_stats(employee_id: int) -> dict:
    operations = [
        operation
        for operation in load_staff_operations().get("operations", [])
        if operation.get("actor", {}).get("id") == employee_id
    ]
    add_stock_count = sum(1 for operation in operations if operation.get("action") == "add_product_stock")
    add_username_count = sum(1 for operation in operations if operation.get("action") == "add_username")
    last_operation = max(
        (operation.get("created_at", 0) for operation in operations),
        default=0,
    )
    return {
        "total": len(operations),
        "add_stock": add_stock_count,
        "add_username": add_username_count,
        "last_operation": last_operation,
    }


def format_employee_details(employee: dict) -> str:
    employee_id = int(employee.get("id"))
    stats = get_employee_stats(employee_id)
    username = employee.get("username") or "لا يوجد"
    name = employee.get("name") or "غير معروف"

    return (
        "تفاصيل الموظف.\n\n"
        f"الاسم: {name}\n"
        f"اليوزر: @{username}\n"
        f"الايدي: {employee_id}\n"
        f"وقت التوظيف: {format_timestamp(employee.get('added_at'))}\n\n"
        "الاحصائيات:\n"
        f"اجمالي العمليات: {stats['total']}\n"
        f"اضافة مخزون منتجات: {stats['add_stock']}\n"
        f"اضافة يوزرات: {stats['add_username']}\n"
        f"اخر عملية: {format_timestamp(stats['last_operation'])}"
    )


def load_products() -> list[dict]:
    if not os.path.exists(PRODUCTS_FILE):
        return []

    with open(PRODUCTS_FILE, "r", encoding="utf-8") as products_file:
        try:
            products = json.load(products_file)
        except json.JSONDecodeError:
            LOGGER.warning("%s is not valid JSON. Starting with an empty list.", PRODUCTS_FILE)
            return []

    return products if isinstance(products, list) else []


def safe_save_json(filepath: str, data: dict | list) -> None:
    temp_filepath = filepath + ".tmp"
    try:
        with open(temp_filepath, "w", encoding="utf-8") as temp_file:
            json.dump(data, temp_file, ensure_ascii=False, indent=2)
        os.replace(temp_filepath, filepath)
    except Exception as e:
        LOGGER.error("Error saving JSON to %s: %s", filepath, e)
        if os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
            except Exception:
                pass
        raise


def save_products(products: list[dict]) -> None:
    safe_save_json(PRODUCTS_FILE, products)


def load_users() -> dict:
    if not os.path.exists(USERS_FILE):
        return {}

    with open(USERS_FILE, "r", encoding="utf-8") as users_file:
        try:
            users = json.load(users_file)
        except json.JSONDecodeError:
            LOGGER.warning("%s is not valid JSON. Starting with an empty dict.", USERS_FILE)
            return {}

    return users if isinstance(users, dict) else {}


def save_users(users: dict) -> None:
    safe_save_json(USERS_FILE, users)


def is_user_banned(user_id: int | None) -> bool:
    if not user_id:
        return False
    user = load_users().get(str(user_id), {})
    return bool(user.get("banned"))


def ban_user(user_id: int, reason: str, details: dict | None = None) -> None:
    users = load_users()
    user = users.setdefault(str(user_id), {})
    user["banned"] = True
    user["ban_reason"] = reason
    user["banned_at"] = int(time.time())
    if details:
        user["ban_details"] = details
    save_users(users)


def load_bot_users() -> dict:
    if not os.path.exists(BOT_USERS_FILE):
        return {"next_number": 1, "users": []}

    with open(BOT_USERS_FILE, "r", encoding="utf-8") as bot_users_file:
        try:
            data = json.load(bot_users_file)
        except json.JSONDecodeError:
            LOGGER.warning("%s is not valid JSON. Starting with an empty list.", BOT_USERS_FILE)
            return {"next_number": 1, "users": []}

    if not isinstance(data, dict):
        return {"next_number": 1, "users": []}
    if not isinstance(data.get("users"), list):
        data["users"] = []
    if not isinstance(data.get("next_number"), int):
        data["next_number"] = len(data["users"]) + 1
    return data


def save_bot_users(data: dict) -> None:
    safe_save_json(BOT_USERS_FILE, data)


def load_user_operations() -> dict:
    if not os.path.exists(USER_OPERATIONS_FILE):
        return {"next_order_number": 1, "operations": []}

    with open(USER_OPERATIONS_FILE, "r", encoding="utf-8") as operations_file:
        try:
            data = json.load(operations_file)
        except json.JSONDecodeError:
            LOGGER.warning("%s is not valid JSON. Starting with an empty log.", USER_OPERATIONS_FILE)
            return {"next_order_number": 1, "operations": []}

    if not isinstance(data, dict):
        return {"next_order_number": 1, "operations": []}
    if not isinstance(data.get("operations"), list):
        data["operations"] = []
    if not isinstance(data.get("next_order_number"), int):
        data["next_order_number"] = 1
    return data


def save_user_operations(data: dict) -> None:
    safe_save_json(USER_OPERATIONS_FILE, data)


def load_archive() -> dict:
    if not os.path.exists(ARCHIVE_FILE):
        return {"sold_usernames": []}

    with open(ARCHIVE_FILE, "r", encoding="utf-8") as archive_file:
        try:
            data = json.load(archive_file)
        except json.JSONDecodeError:
            LOGGER.warning("%s is not valid JSON. Starting with an empty archive.", ARCHIVE_FILE)
            return {"sold_usernames": []}

    if not isinstance(data, dict):
        return {"sold_usernames": []}
    if not isinstance(data.get("sold_usernames"), list):
        data["sold_usernames"] = []
    return data


def save_archive(data: dict) -> None:
    safe_save_json(ARCHIVE_FILE, data)


def load_employees() -> dict:
    if not os.path.exists(EMPLOYEES_FILE):
        return {"employees": []}

    with open(EMPLOYEES_FILE, "r", encoding="utf-8") as employees_file:
        try:
            data = json.load(employees_file)
        except json.JSONDecodeError:
            LOGGER.warning("%s is not valid JSON. Starting with an empty employee list.", EMPLOYEES_FILE)
            return {"employees": []}

    if not isinstance(data, dict):
        return {"employees": []}
    if not isinstance(data.get("employees"), list):
        data["employees"] = []
    ensure_employee_info(data)
    return data


def save_employees(data: dict) -> None:
    safe_save_json(EMPLOYEES_FILE, data)


def ensure_employee_info(data: dict) -> None:
    changed = False
    for employee in data.get("employees", []):
        known_info = get_known_user_info(int(employee.get("id", 0)))
        if not employee.get("name"):
            employee["name"] = known_info["name"]
            changed = True
        if "username" not in employee:
            employee["username"] = known_info["username"]
            changed = True

    if changed:
        save_employees(data)


def load_staff_operations() -> dict:
    if not os.path.exists(STAFF_OPERATIONS_FILE):
        return {"operations": []}

    with open(STAFF_OPERATIONS_FILE, "r", encoding="utf-8") as operations_file:
        try:
            data = json.load(operations_file)
        except json.JSONDecodeError:
            LOGGER.warning("%s is not valid JSON. Starting with an empty log.", STAFF_OPERATIONS_FILE)
            return {"operations": []}

    if not isinstance(data, dict):
        return {"operations": []}
    if not isinstance(data.get("operations"), list):
        data["operations"] = []
    return data


def save_staff_operations(data: dict) -> None:
    safe_save_json(STAFF_OPERATIONS_FILE, data)


def load_topups() -> dict:
    if not os.path.exists(TOPUPS_FILE):
        return {"topups": []}

    with open(TOPUPS_FILE, "r", encoding="utf-8") as topups_file:
        try:
            data = json.load(topups_file)
        except json.JSONDecodeError:
            LOGGER.warning("%s is not valid JSON. Starting with an empty list.", TOPUPS_FILE)
            return {"topups": []}

    if not isinstance(data, dict):
        return {"topups": []}
    if not isinstance(data.get("topups"), list):
        data["topups"] = []
    return data


def save_topups(data: dict) -> None:
    safe_save_json(TOPUPS_FILE, data)


def load_support_tickets() -> dict:
    if not os.path.exists(SUPPORT_TICKETS_FILE):
        return {"next_ticket_number": 1, "tickets": []}

    with open(SUPPORT_TICKETS_FILE, "r", encoding="utf-8") as tickets_file:
        try:
            data = json.load(tickets_file)
        except json.JSONDecodeError:
            LOGGER.warning("%s is not valid JSON. Starting with an empty list.", SUPPORT_TICKETS_FILE)
            return {"next_ticket_number": 1, "tickets": []}

    if not isinstance(data, dict):
        return {"next_ticket_number": 1, "tickets": []}
    if not isinstance(data.get("tickets"), list):
        data["tickets"] = []
    if not isinstance(data.get("next_ticket_number"), int):
        data["next_ticket_number"] = len(data["tickets"]) + 1
    return data


def save_support_tickets(data: dict) -> None:
    safe_save_json(SUPPORT_TICKETS_FILE, data)


def load_bot_settings() -> dict:
    if not os.path.exists(BOT_SETTINGS_FILE):
        return {"required_channel": None}

    with open(BOT_SETTINGS_FILE, "r", encoding="utf-8") as settings_file:
        try:
            data = json.load(settings_file)
        except json.JSONDecodeError:
            LOGGER.warning("%s is not valid JSON. Starting with default settings.", BOT_SETTINGS_FILE)
            return {"required_channel": None}

    if not isinstance(data, dict):
        return {"required_channel": None}
    if "required_channel" not in data:
        data["required_channel"] = None
    return data


def save_bot_settings(data: dict) -> None:
    safe_save_json(BOT_SETTINGS_FILE, data)


def get_payment_setting(key: str, default: str = "") -> str:
    settings = load_bot_settings()
    payment_settings = settings.get("payment_settings", {})
    if isinstance(payment_settings, dict) and key in payment_settings and payment_settings[key] is not None:
        val = str(payment_settings[key]).strip()
        if val:
            return val
    return os.getenv(key, default).strip()


def update_env_file_key(key: str, value: str) -> None:
    if not os.path.exists(ENV_FILE):
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")
        return

    lines = []
    key_found = False
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith(f"{key}=") or line.strip().startswith(f"{key} ="):
                lines.append(f"{key}={value}\n")
                key_found = True
            else:
                lines.append(line)

    if not key_found:
        lines.append(f"{key}={value}\n")

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines)


def save_payment_setting(key: str, value: str | bool) -> None:
    settings = load_bot_settings()
    if "payment_settings" not in settings or not isinstance(settings["payment_settings"], dict):
        settings["payment_settings"] = {}
    settings["payment_settings"][key] = value
    save_bot_settings(settings)

    if isinstance(value, str):
        os.environ[key] = value
        update_env_file_key(key, value)


def is_nowpayments_enabled() -> bool:
    settings = load_bot_settings()
    payment_settings = settings.get("payment_settings", {})
    if isinstance(payment_settings, dict) and "nowpayments_enabled" in payment_settings:
        return bool(payment_settings["nowpayments_enabled"])
    return bool(get_nowpayments_api_key() or (get_nowpayments_email() and get_nowpayments_password()))


def is_tap_enabled() -> bool:
    settings = load_bot_settings()
    payment_settings = settings.get("payment_settings", {})
    if isinstance(payment_settings, dict) and "tap_enabled" in payment_settings:
        return bool(payment_settings["tap_enabled"])
    return bool(get_tap_secret_key())


def format_payment_settings_overview() -> str:
    now_enabled = is_nowpayments_enabled()
    tap_enabled = is_tap_enabled()

    now_status = "🟢 مفعل" if now_enabled else "🔴 معطل"
    tap_status = "🟢 مفعل" if tap_enabled else "🔴 معطل"

    now_key = get_nowpayments_api_key()
    now_key_masked = (now_key[:4] + "***" + now_key[-4:]) if len(now_key) > 8 else (now_key or "غير محدد")
    now_email = get_nowpayments_email() or "غير محدد"
    now_curr = get_nowpayments_price_currency().upper()

    tap_key = get_tap_secret_key()
    tap_key_masked = (tap_key[:6] + "***" + tap_key[-4:]) if len(tap_key) > 10 else (tap_key or "غير محدد")
    tap_curr = get_tap_currency()
    tap_source = get_tap_source_id()
    rate = get_topup_credit_rate()

    return (
        "⚙️ <b>إعدادات وتستطيب طرق الدفع:</b>\n\n"
        "💳 <b>NOWPayments (عملات رقمية):</b>\n"
        f"• الحالة: {now_status}\n"
        f"• API Key: <code>{now_key_masked}</code>\n"
        f"• Email: <code>{now_email}</code>\n"
        f"• العملة: <code>{now_curr}</code>\n\n"
        "💸 <b>Tap Payments (بطاقة / Apple Pay):</b>\n"
        f"• الحالة: {tap_status}\n"
        f"• Secret Key: <code>{tap_key_masked}</code>\n"
        f"• العملة: <code>{tap_curr}</code>\n"
        f"• Source ID: <code>{tap_source}</code>\n\n"
        f"💱 <b>معدل شحن الرصيد (Topup Rate):</b> <code>{rate}</code>\n\n"
        "👇 اختر البوابة أو الخاصية التي تريد تعديلها وتستطيبها:"
    )


def admin_payment_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💳 إعدادات NOWPayments", callback_data="admin_nowpayments_menu")],
            [InlineKeyboardButton("💸 إعدادات Tap Payments", callback_data="admin_tap_menu")],
            [InlineKeyboardButton("💱 تعديل معدل الشحن (Rate)", callback_data="edit_payment_setting:TOPUP_CREDIT_RATE")],
            [InlineKeyboardButton("↩️ رجوع للوحة الادمن", callback_data="admin_menu")],
        ]
    )


def format_nowpayments_settings() -> str:
    enabled = is_nowpayments_enabled()
    status = "🟢 مفعل" if enabled else "🔴 معطل"
    api_key = get_nowpayments_api_key() or "غير محدد"
    email = get_nowpayments_email() or "غير محدد"
    pwd = ("******" if get_nowpayments_password() else "غير محدد")
    curr = get_nowpayments_price_currency().upper()

    return (
        "💳 <b>إعدادات بوابة NOWPayments</b>\n\n"
        f"• حالة البوابة: {status}\n"
        f"• API Key: <code>{api_key}</code>\n"
        f"• الحساب (Email): <code>{email}</code>\n"
        f"• كلمة المرور (Password): <code>{pwd}</code>\n"
        f"• العملة المستخدمة: <code>{curr}</code>\n\n"
        "👇 اختر الإعداد المراد تعديله:"
    )


def admin_nowpayments_keyboard() -> InlineKeyboardMarkup:
    enabled = is_nowpayments_enabled()
    toggle_text = "🔴 تعطيل البوابة" if enabled else "🟢 تفعيل البوابة"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(toggle_text, callback_data="admin_toggle_nowpayments")],
            [InlineKeyboardButton("✏️ تعديل API Key", callback_data="edit_payment_setting:NOWPAYMENTS_API_KEY")],
            [InlineKeyboardButton("✏️ تعديل الإيميل (Email)", callback_data="edit_payment_setting:NOWPAYMENTS_EMAIL")],
            [InlineKeyboardButton("✏️ تعديل كلمة المرور (Password)", callback_data="edit_payment_setting:NOWPAYMENTS_PASSWORD")],
            [InlineKeyboardButton("↩️ رجوع لإعدادات الدفع", callback_data="admin_payment_settings")],
        ]
    )


def format_tap_settings() -> str:
    enabled = is_tap_enabled()
    status = "🟢 مفعل" if enabled else "🔴 معطل"
    secret_key = get_tap_secret_key() or "غير محدد"
    curr = get_tap_currency()
    source_id = get_tap_source_id()

    return (
        "💸 <b>إعدادات بوابة Tap Payments</b>\n\n"
        f"• حالة البوابة: {status}\n"
        f"• Secret Key: <code>{secret_key}</code>\n"
        f"• العملة: <code>{curr}</code>\n"
        f"• Source ID: <code>{source_id}</code>\n\n"
        "👇 اختر الإعداد المراد تعديله:"
    )


def admin_tap_keyboard() -> InlineKeyboardMarkup:
    enabled = is_tap_enabled()
    toggle_text = "🔴 تعطيل البوابة" if enabled else "🟢 تفعيل البوابة"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(toggle_text, callback_data="admin_toggle_tap")],
            [InlineKeyboardButton("✏️ تعديل Secret Key", callback_data="edit_payment_setting:TAP_SECRET_KEY")],
            [InlineKeyboardButton("↩️ رجوع لإعدادات الدفع", callback_data="admin_payment_settings")],
        ]
    )


def get_required_channel() -> dict | None:
    channel = load_bot_settings().get("required_channel")
    return channel if isinstance(channel, dict) and channel.get("chat_id") else None


def normalize_required_channel(raw_channel: str) -> dict | None:
    value = raw_channel.strip()
    if not value:
        return None

    if value.startswith("https://t.me/"):
        value = value.removeprefix("https://t.me/").strip("/")
    elif value.startswith("http://t.me/"):
        value = value.removeprefix("http://t.me/").strip("/")
    elif value.startswith("t.me/"):
        value = value.removeprefix("t.me/").strip("/")

    if value.startswith("@"):
        username = value[1:].strip()
        if not username:
            return None
        return {"chat_id": f"@{username}", "username": username}

    if value.lstrip("-").isdigit():
        return {"chat_id": int(value), "username": ""}

    username = value.strip()
    if username:
        return {"chat_id": f"@{username}", "username": username}
    return None


def get_required_channel_url(channel: dict) -> str | None:
    username = channel.get("username")
    if username:
        return f"https://t.me/{username}"
    return None


def format_required_channel_settings() -> str:
    channel = get_required_channel()
    if not channel:
        return (
            "📢 الاشتراك الاجباري.\n\n"
            "الحالة: معطل\n\n"
            "تقدر تحدد قناة عامة مثل @channelname. لازم تضيف البوت مشرف في القناة حتى يقدر يتحقق من الاشتراك."
        )

    channel_label = channel.get("chat_id")
    if channel.get("username"):
        channel_label = f"@{channel['username']}"
    return (
        "📢 الاشتراك الاجباري.\n\n"
        "الحالة: مفعل\n"
        f"القناة الحالية: {channel_label}\n\n"
        "تأكد أن البوت مشرف في القناة حتى يتم التحقق بشكل صحيح."
    )


def required_channel_message(channel: dict) -> str:
    channel_label = f"@{channel['username']}" if channel.get("username") else "القناة المطلوبة"
    return (
        "🔒 يلزم الاشتراك في القناة قبل استخدام البوت.\n\n"
        f"📢 القناة: {channel_label}\n"
        "بعد الاشتراك اضغط زر التحقق."
    )


async def is_user_subscribed_to_required_channel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    if is_admin(update) or is_employee(update):
        return True

    user = update.effective_user
    channel = get_required_channel()
    if not user or not channel:
        return True

    try:
        member = await context.bot.get_chat_member(channel["chat_id"], user.id)
    except BadRequest as error:
        LOGGER.warning("Could not check required channel membership: %s", error)
        return False

    if member.status in {"creator", "administrator", "member"}:
        return True
    return bool(getattr(member, "is_member", False))


async def prompt_required_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    channel = get_required_channel()
    if not channel:
        return

    text = required_channel_message(channel)
    reply_markup = required_channel_join_keyboard(channel)
    if update.callback_query:
        await edit_message(update.callback_query, text, reply_markup=reply_markup)
    elif update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)


async def ensure_required_channel_subscription(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    if await is_user_subscribed_to_required_channel(update, context):
        return True

    await prompt_required_channel(update, context)
    return False


def create_ticket_number(data: dict) -> str:
    number = f"TCK-{data['next_ticket_number']:06d}"
    data["next_ticket_number"] += 1
    return number


def get_ticket(ticket_id: str) -> dict | None:
    for ticket in load_support_tickets().get("tickets", []):
        if ticket.get("id") == ticket_id:
            return ticket
    return None


def update_ticket(ticket_id: str, updates: dict) -> None:
    data = load_support_tickets()
    for ticket in data.get("tickets", []):
        if ticket.get("id") == ticket_id:
            ticket.update(updates)
            ticket["updated_at"] = int(time.time())
            save_support_tickets(data)
            return


def add_ticket_message(ticket_id: str, message: dict) -> dict | None:
    data = load_support_tickets()
    for ticket in data.get("tickets", []):
        if ticket.get("id") != ticket_id:
            continue
        message.setdefault("id", make_short_id())
        message.setdefault("created_at", int(time.time()))
        ticket.setdefault("messages", []).append(message)
        ticket["updated_at"] = int(time.time())
        if ticket.get("status") != "closed":
            ticket["status"] = "open"
        save_support_tickets(data)
        return ticket
    return None


def create_support_ticket(user, category: str, messages: list[dict]) -> dict:
    data = load_support_tickets()
    now = int(time.time())
    ticket = {
        "id": make_short_id(),
        "number": create_ticket_number(data),
        "status": "open",
        "category": category,
        "category_label": SUPPORT_CATEGORIES.get(category, "💬 دعم"),
        "user_id": user.id,
        "user_name": get_user_display_name(user),
        "username": user.username or "",
        "created_at": now,
        "updated_at": now,
        "messages": messages,
    }
    data["tickets"].append(ticket)
    save_support_tickets(data)
    return ticket


def get_user_tickets(user_id: int) -> list[dict]:
    return [
        ticket
        for ticket in load_support_tickets().get("tickets", [])
        if ticket.get("user_id") == user_id
    ]


def get_staff_visible_tickets() -> list[dict]:
    tickets = load_support_tickets().get("tickets", [])
    return sorted(
        tickets,
        key=lambda ticket: (
            1 if ticket.get("status") == "closed" else 0,
            -int(ticket.get("updated_at", ticket.get("created_at", 0))),
        ),
    )


def get_topup(payment_id: str) -> dict | None:
    for topup in load_topups().get("topups", []):
        if str(topup.get("payment_id")) == str(payment_id):
            return topup
    return None


def get_topup_by_id(topup_id: str) -> dict | None:
    for topup in load_topups().get("topups", []):
        if str(topup.get("id")) == str(topup_id):
            return topup
    return None


def get_latest_uncredited_topup(user_id: int) -> dict | None:
    topups = [
        topup
        for topup in load_topups().get("topups", [])
        if topup.get("user_id") == user_id and not topup.get("credited")
    ]
    if not topups:
        return None
    return max(topups, key=lambda topup: int(topup.get("created_at", 0)))


def get_topup_expires_at(topup: dict) -> int:
    try:
        return int(topup.get("expires_at") or 0)
    except (TypeError, ValueError):
        return 0


def is_topup_expired(topup: dict, now: int | None = None) -> bool:
    expires_at = get_topup_expires_at(topup)
    if not expires_at:
        created_at = int(topup.get("created_at", 0) or 0)
        expires_at = created_at + TOPUP_LINK_TTL_SECONDS if created_at else 0
    return bool(expires_at and (now or int(time.time())) >= expires_at)


def expire_topup_if_needed(topup: dict, now: int | None = None) -> bool:
    if topup.get("credited"):
        return False
    if str(topup.get("payment_status") or "").lower() == "expired":
        return False
    if not is_topup_expired(topup, now):
        return False

    update_topup_by_id(
        str(topup["id"]),
        {
            "payment_status": "expired",
            "expired_at": get_topup_expires_at(topup) or int(topup.get("created_at", 0) or 0) + TOPUP_LINK_TTL_SECONDS,
            "last_check_note": "expired_after_20_minutes",
        },
    )
    return True


def get_pending_invoice_topups() -> list[dict]:
    now = int(time.time())
    return [
        topup
        for topup in load_topups().get("topups", [])
        if not topup.get("credited")
        and not is_topup_expired(topup, now)
        and str(topup.get("payment_status") or "").lower() != "expired"
        and (
            topup.get("method") == "tap_charge"
            or topup.get("tap_charge_id")
        )
    ]


def update_topup(payment_id: str, updates: dict) -> None:
    data = load_topups()
    for topup in data.get("topups", []):
        if str(topup.get("payment_id")) == str(payment_id):
            topup.update(updates)
            topup["updated_at"] = int(time.time())
            save_topups(data)
            return


def update_topup_by_id(topup_id: str, updates: dict) -> None:
    data = load_topups()
    for topup in data.get("topups", []):
        if str(topup.get("id")) == str(topup_id):
            topup.update(updates)
            topup["updated_at"] = int(time.time())
            save_topups(data)
            return


def add_topup(topup: dict) -> None:
    data = load_topups()
    data["topups"].append(topup)
    save_topups(data)


def get_topup_credit_rate() -> float:
    return parse_amount(get_payment_setting(TOPUP_CREDIT_RATE_ENV_NAME, "1"), default=1)


def get_nowpayments_api_key() -> str:
    return get_payment_setting(NOWPAYMENTS_API_KEY_ENV_NAME, "")


def get_nowpayments_jwt_token() -> str:
    return get_payment_setting(NOWPAYMENTS_JWT_TOKEN_ENV_NAME, "")


def get_nowpayments_email() -> str:
    return get_payment_setting(NOWPAYMENTS_EMAIL_ENV_NAME, "")


def get_nowpayments_password() -> str:
    return get_payment_setting(NOWPAYMENTS_PASSWORD_ENV_NAME, "")


def get_nowpayments_price_currency() -> str:
    return os.getenv(NOWPAYMENTS_PRICE_CURRENCY_ENV_NAME, "usd").strip().lower() or "usd"


def nowpayments_auth_request(email: str, password: str) -> dict:
    data = json.dumps({"email": email, "password": password}).encode("utf-8")
    request = urllib.request.Request(
        f"{NOWPAYMENTS_API_BASE}/auth",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "StoreBot/1.0 (+https://api.nowpayments.io)",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"NOWPayments auth HTTP {error.code}: {details[:300]}") from error


def get_nowpayments_bearer_token() -> str:
    now = int(time.time())
    cached_token = NOWPAYMENTS_JWT_CACHE.get("token", "")
    if cached_token and int(NOWPAYMENTS_JWT_CACHE.get("expires_at", 0)) > now:
        return cached_token

    email = get_nowpayments_email()
    password = get_nowpayments_password()
    if email and password:
        auth = nowpayments_auth_request(email, password)
        token = auth.get("token") or auth.get("jwt") or auth.get("access_token")
        if not token:
            raise RuntimeError("NOWPayments auth did not return a token")
        NOWPAYMENTS_JWT_CACHE["token"] = str(token)
        NOWPAYMENTS_JWT_CACHE["expires_at"] = now + 240
        return str(token)

    token = get_nowpayments_jwt_token()
    if token:
        return token

    raise RuntimeError(
        f"Missing {NOWPAYMENTS_EMAIL_ENV_NAME}/{NOWPAYMENTS_PASSWORD_ENV_NAME} "
        f"or {NOWPAYMENTS_JWT_TOKEN_ENV_NAME} in {ENV_FILE}"
    )


def nowpayments_request(
    method: str,
    path: str,
    payload: dict | None = None,
    use_bearer_token: bool = False,
) -> dict:
    api_key = get_nowpayments_api_key()
    if not api_key:
        raise RuntimeError(f"Missing {NOWPAYMENTS_API_KEY_ENV_NAME} in {ENV_FILE}")

    data = None
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "StoreBot/1.0 (+https://api.nowpayments.io)",
    }
    if use_bearer_token:
        jwt_token = get_nowpayments_bearer_token()
        headers["Authorization"] = f"Bearer {jwt_token}"

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        f"{NOWPAYMENTS_API_BASE}{path}",
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="ignore")
        if use_bearer_token and "INVALID_AUTH_TOKEN" in details:
            NOWPAYMENTS_JWT_CACHE["token"] = ""
            NOWPAYMENTS_JWT_CACHE["expires_at"] = 0
        if "Cloudflare" in details or "Attention Required" in details:
            raise RuntimeError(
                f"NOWPayments HTTP {error.code}: Cloudflare blocked this request"
            ) from error
        raise RuntimeError(f"NOWPayments HTTP {error.code}: {details[:300]}") from error


def create_nowpayments_payment(
    user_id: int,
    amount: float,
    pay_currency: str,
) -> dict:
    price_currency = os.getenv(NOWPAYMENTS_PRICE_CURRENCY_ENV_NAME, "usd").strip().lower()
    order_id = f"TOPUP-{user_id}-{int(time.time())}-{make_short_id()}"
    return nowpayments_request(
        "POST",
        "/payment",
        {
            "price_amount": amount,
            "price_currency": price_currency,
            "pay_currency": pay_currency,
            "order_id": order_id,
            "order_description": f"Wallet top-up for Telegram user {user_id}",
        },
    )


def create_nowpayments_invoice(user_id: int, amount: float) -> dict:
    payload = {
        "price_amount": amount,
        "price_currency": get_nowpayments_price_currency(),
        "order_id": f"TOPUP-{user_id}-{int(time.time())}-{make_short_id()}",
        "order_description": f"Wallet top-up for Telegram user {user_id}",
    }

    success_url = os.getenv(NOWPAYMENTS_SUCCESS_URL_ENV_NAME, "").strip()
    cancel_url = os.getenv(NOWPAYMENTS_CANCEL_URL_ENV_NAME, "").strip()
    if success_url:
        payload["success_url"] = success_url
    if cancel_url:
        payload["cancel_url"] = cancel_url

    invoice = nowpayments_request("POST", "/invoice", payload)
    invoice.setdefault("order_id", payload["order_id"])
    return invoice


def get_nowpayments_payment(payment_id: str) -> dict:
    return nowpayments_request("GET", f"/payment/{payment_id}")


def collect_nowpayments_payment_candidates(response) -> list[dict]:
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]

    if not isinstance(response, dict):
        return []

    candidates = [response]
    for key in ("data", "payments", "result", "items"):
        value = response.get(key)
        if isinstance(value, list):
            candidates.extend(item for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            candidates.extend(collect_nowpayments_payment_candidates(value))

    return candidates


def list_nowpayments_payments(limit: int = 50, page: int = 0) -> dict:
    query = urllib.parse.urlencode(
        {
            "limit": limit,
            "page": page,
            "orderBy": "DESC",
        }
    )
    return nowpayments_request("GET", f"/payment?{query}", use_bearer_token=True)


def find_nowpayments_payment_for_topup(topup: dict) -> dict | None:
    invoice = topup.get("raw_invoice") if isinstance(topup.get("raw_invoice"), dict) else {}
    expected_invoice_id = str(topup.get("invoice_id") or invoice.get("id") or "").strip()
    expected_order_id = str(topup.get("order_id") or invoice.get("order_id") or "").strip()

    for page in range(3):
        response = list_nowpayments_payments(page=page)
        for candidate in collect_nowpayments_payment_candidates(response):
            payment_invoice_id = str(candidate.get("invoice_id") or candidate.get("invoiceId") or "").strip()
            payment_order_id = str(candidate.get("order_id") or candidate.get("orderId") or "").strip()
            if expected_invoice_id and payment_invoice_id == expected_invoice_id:
                payment_id = candidate.get("payment_id") or candidate.get("paymentId")
                return get_nowpayments_payment(str(payment_id)) if payment_id else candidate
            if expected_order_id and payment_order_id == expected_order_id:
                payment_id = candidate.get("payment_id") or candidate.get("paymentId")
                return get_nowpayments_payment(str(payment_id)) if payment_id else candidate

        if len(collect_nowpayments_payment_candidates(response)) < 50:
            break

    return None


def payment_matches_topup(payment: dict, topup: dict) -> bool:
    invoice = topup.get("raw_invoice") if isinstance(topup.get("raw_invoice"), dict) else {}
    expected_order_id = str(topup.get("order_id") or invoice.get("order_id") or "")
    expected_invoice_id = str(topup.get("invoice_id") or "")
    payment_order_id = str(payment.get("order_id") or "")
    payment_invoice_id = str(payment.get("invoice_id") or "")

    if expected_order_id and payment_order_id:
        return expected_order_id == payment_order_id
    if expected_invoice_id and payment_invoice_id:
        return expected_invoice_id == payment_invoice_id
    if topup.get("payment_id") and payment.get("payment_id"):
        return str(topup.get("payment_id")) == str(payment.get("payment_id"))

    return False


def get_topup_payment_id(topup: dict) -> str | None:
    for key in ("payment_id", "paymentId"):
        if topup.get(key):
            return str(topup[key])

    for container_key in ("raw_status", "raw_payment", "raw_invoice"):
        container = topup.get(container_key)
        if not isinstance(container, dict):
            continue
        for key in ("payment_id", "paymentId"):
            if container.get(key):
                return str(container[key])

    return None


def get_tap_secret_key() -> str:
    return get_payment_setting(TAP_SECRET_KEY_ENV_NAME, "")


def get_tap_currency() -> str:
    return os.getenv(TAP_CURRENCY_ENV_NAME, "SAR").strip().upper() or "SAR"


def get_tap_source_id() -> str:
    return os.getenv(TAP_SOURCE_ID_ENV_NAME, "src_all").strip() or "src_all"


def tap_request(method: str, path: str, payload: dict | None = None) -> dict:
    secret_key = get_tap_secret_key()
    if not secret_key:
        raise RuntimeError(f"Missing {TAP_SECRET_KEY_ENV_NAME} in {ENV_FILE}")

    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{TAP_API_BASE}{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "StoreBot/1.0",
        },
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Tap Payments HTTP {error.code}: {details[:300]}") from error


def create_tap_charge(
    user,
    amount: float,
    description: str | None = None,
    reference_prefix: str = "TAP-PAY",
    metadata: dict | None = None,
) -> dict:
    reference_id = f"{reference_prefix}-{user.id}-{int(time.time())}-{make_short_id()}"
    first_name = (getattr(user, "first_name", None) or "Telegram").strip()[:40]
    last_name = (getattr(user, "last_name", None) or "User").strip()[:40]
    customer = {
        "first_name": first_name,
        "last_name": last_name,
    }
    customer_email = os.getenv(TAP_CUSTOMER_EMAIL_ENV_NAME, "").strip()
    customer["email"] = customer_email or f"telegram-{user.id}@example.com"

    phone_country_code = os.getenv(TAP_CUSTOMER_PHONE_COUNTRY_CODE_ENV_NAME, "").strip()
    phone_number = os.getenv(TAP_CUSTOMER_PHONE_NUMBER_ENV_NAME, "").strip()
    if phone_country_code and phone_number:
        customer["phone"] = {
            "country_code": phone_country_code,
            "number": phone_number,
        }

    payload = {
        "amount": round(amount, 2),
        "currency": get_tap_currency(),
        "customer_initiated": True,
        "threeDSecure": True,
        "save_card": False,
        "description": description or f"Telegram order payment for user {user.id}",
        "metadata": {
            "telegram_user_id": str(user.id),
            "payment_reference": reference_id,
            **(metadata or {}),
        },
        "reference": {
            "transaction": reference_id,
            "order": reference_id,
        },
        "receipt": {
            "email": False,
            "sms": False,
        },
        "customer": customer,
        "source": {
            "id": get_tap_source_id(),
        },
        "redirect": {
            "url": os.getenv(TAP_REDIRECT_URL_ENV_NAME, "https://example.com").strip()
            or "https://example.com",
        },
    }

    post_url = os.getenv(TAP_POST_URL_ENV_NAME, "").strip()
    if post_url:
        payload["post"] = {"url": post_url}

    charge = tap_request("POST", "/charges/", payload)
    charge.setdefault("reference_id", reference_id)
    return charge


def get_tap_payment_url(charge: dict) -> str:
    transaction = charge.get("transaction")
    if isinstance(transaction, dict) and transaction.get("url"):
        return str(transaction["url"])
    return str(charge.get("redirect_url") or charge.get("url") or "")


def get_tap_charge(charge_id: str) -> dict:
    return tap_request("GET", f"/charges/{charge_id}")


def get_payment_status(data: dict) -> str:
    return str(data.get("payment_status") or data.get("status") or "").lower()


def is_success_payment_status(status: str | None) -> bool:
    return str(status or "").lower() in {"finished", "confirmed", "sending", "completed", "captured"}


def tap_charge_matches_topup(charge: dict, topup: dict) -> bool:
    expected_charge_id = str(topup.get("tap_charge_id") or "")
    if expected_charge_id and str(charge.get("id") or "") == expected_charge_id:
        return True

    expected_reference_id = str(topup.get("order_id") or "")
    reference = charge.get("reference") if isinstance(charge.get("reference"), dict) else {}
    return bool(
        expected_reference_id
        and (
            str(reference.get("transaction") or "") == expected_reference_id
            or str(reference.get("order") or "") == expected_reference_id
        )
    )


def get_verified_tap_topup(topup: dict) -> tuple[str, dict] | None:
    if expire_topup_if_needed(topup):
        return None

    tap_charge_id = str(topup.get("tap_charge_id") or "").strip()
    if not tap_charge_id:
        update_topup_by_id(
            str(topup["id"]),
            {
                "payment_status": get_payment_status(topup) or "waiting",
                "last_check_note": "missing_tap_charge_id",
                "last_checked_at": int(time.time()),
            },
        )
        return None

    charge = get_tap_charge(tap_charge_id)
    status = get_payment_status(charge)
    updates = {
        "payment_status": status or "waiting",
        "raw_status": charge,
        "last_check_note": "checked_tap_charge",
        "last_checked_at": int(time.time()),
    }
    update_topup_by_id(str(topup["id"]), updates)

    if status == "captured" and tap_charge_matches_topup(charge, topup):
        return status, charge

    return None


def get_verified_topup_payment(topup: dict) -> tuple[str, dict] | None:
    if topup.get("method") == "tap_charge":
        return get_verified_tap_topup(topup)

    payment_id = get_topup_payment_id(topup)
    current_status = get_payment_status(topup)

    if is_success_payment_status(current_status):
        return current_status, topup.get("raw_status") if isinstance(topup.get("raw_status"), dict) else topup

    if not payment_id:
        invoice_payment = find_nowpayments_payment_for_topup(topup)
        if invoice_payment:
            payment_id = invoice_payment.get("payment_id") or invoice_payment.get("paymentId")
            status = get_payment_status(invoice_payment)
            updates = {
                "payment_status": status or current_status or "waiting",
                "raw_status": invoice_payment,
                "last_check_note": "checked_by_payment_list",
                "last_checked_at": int(time.time()),
            }
            if payment_id:
                updates["payment_id"] = str(payment_id)
            update_topup_by_id(str(topup["id"]), updates)
            if is_success_payment_status(status) and payment_matches_topup(invoice_payment, topup):
                return status, invoice_payment
            if not payment_id:
                return None
        else:
            update_topup_by_id(
                str(topup["id"]),
                {
                    "payment_status": current_status or "waiting",
                    "last_check_note": "payment_not_found_in_api",
                    "last_checked_at": int(time.time()),
                },
            )
            return None

    payment = get_nowpayments_payment(str(payment_id))
    status = get_payment_status(payment)
    if is_success_payment_status(status) and payment_matches_topup(payment, topup):
        return status, payment

    update_topup_by_id(
        str(topup["id"]),
        {
            "payment_status": status or "waiting",
            "raw_status": payment,
            "last_checked_at": int(time.time()),
        },
    )
    return None


def create_order_number(data: dict) -> str:
    order_number = f"ORD-{data['next_order_number']:06d}"
    data["next_order_number"] += 1
    return order_number


def add_user_operation(operation: dict) -> dict:
    data = load_user_operations()
    operation.setdefault("id", make_short_id())
    operation.setdefault("created_at", int(time.time()))
    data["operations"].append(operation)
    save_user_operations(data)
    return operation


def add_purchase_operation(
    user_id: int,
    item_type: str,
    item_name: str,
    amount: float,
    source: str,
    details: dict | None = None,
) -> dict:
    data = load_user_operations()
    operation = {
        "id": make_short_id(),
        "type": "purchase",
        "status": "completed",
        "order_number": create_order_number(data),
        "user_id": user_id,
        "item_type": item_type,
        "item_name": item_name,
        "amount": int(amount) if float(amount).is_integer() else amount,
        "source": source,
        "created_at": int(time.time()),
        "details": details or {},
    }
    data["operations"].append(operation)
    save_user_operations(data)
    return operation


def get_user_purchase_operations(user_id: int) -> list[dict]:
    return [
        operation
        for operation in load_user_operations().get("operations", [])
        if operation.get("user_id") == user_id and operation.get("type") == "purchase"
    ]


def get_user_operation(operation_id: str) -> dict | None:
    for operation in load_user_operations().get("operations", []):
        if operation.get("id") == operation_id:
            return operation
    return None


def find_user_operation_by_reservation(category_id: str, item_id: str) -> dict | None:
    data = load_user_operations()
    for operation in reversed(data.get("operations", [])):
        details = operation.get("details", {})
        if (
            operation.get("type") == "reservation"
            and operation.get("status") == "active"
            and details.get("category_id") == category_id
            and details.get("item_id") == item_id
        ):
            return operation
    return None


def update_user_operation(operation_id: str, updates: dict) -> None:
    data = load_user_operations()
    for operation in data.get("operations", []):
        if operation.get("id") == operation_id:
            operation.update(updates)
            operation["updated_at"] = int(time.time())
            save_user_operations(data)
            return


def user_has_active_reservation(user_id: int) -> bool:
    for category in get_username_categories():
        for item in category.get("items", []):
            if item.get("status") != "reserved":
                continue
            reservation = item.get("reservation", {})
            if reservation.get("user_id") == user_id:
                return True
    return False


def get_username_re_reservation_block_remaining(
    user_id: int,
    category_id: str,
    item_id: str,
) -> int:
    data = load_user_operations()
    now = int(time.time())

    for operation in reversed(data.get("operations", [])):
        details = operation.get("details", {})
        if (
            operation.get("type") == "reservation"
            and operation.get("status") == "cancelled"
            and operation.get("user_id") == user_id
            and details.get("category_id") == category_id
            and details.get("item_id") == item_id
        ):
            cancelled_at = int(operation.get("cancelled_at", operation.get("updated_at", 0)))
            remaining = RESERVATION_RECANCEL_BLOCK_SECONDS - (now - cancelled_at)
            return max(remaining, 0)

    return 0


def get_username_repurchase_block_remaining(
    user_id: int,
    category_id: str,
    item_id: str,
) -> int:
    now = int(time.time())

    for topup in reversed(load_topups().get("topups", [])):
        purchase = topup.get("purchase", {})
        if not isinstance(purchase, dict):
            continue
        if (
            topup.get("kind") == "direct_purchase"
            and purchase.get("type") == "username"
            and topup.get("user_id") == user_id
            and purchase.get("category_id") == category_id
            and purchase.get("item_id") == item_id
        ):
            created_at = int(topup.get("created_at", 0) or 0)
            remaining = USERNAME_REPURCHASE_BLOCK_SECONDS - (now - created_at)
            return max(remaining, 0)

    return 0


def get_recent_username_purchase_attempts(
    user_id: int,
    window_seconds: int = USERNAME_ABUSE_WINDOW_SECONDS,
) -> list[dict]:
    now = int(time.time())
    attempts = []

    for topup in load_topups().get("topups", []):
        purchase = topup.get("purchase", {})
        if not isinstance(purchase, dict):
            continue
        if (
            topup.get("kind") == "direct_purchase"
            and purchase.get("type") == "username"
            and topup.get("user_id") == user_id
        ):
            created_at = int(topup.get("created_at", 0) or 0)
            if created_at and now - created_at <= window_seconds:
                attempts.append(
                    {
                        "created_at": created_at,
                        "category_id": purchase.get("category_id"),
                        "item_id": purchase.get("item_id"),
                        "item_name": purchase.get("item_name", "يوزر بدون اسم"),
                        "payment_id": purchase.get("payment_id") or topup.get("id"),
                    }
                )

    return attempts


def should_ban_for_username_purchase_attempt(
    user_id: int,
    category_id: str,
    item_id: str,
) -> tuple[bool, list[dict]]:
    attempts = get_recent_username_purchase_attempts(user_id)
    seen_items = {
        (attempt.get("category_id"), attempt.get("item_id"))
        for attempt in attempts
    }
    seen_items.add((category_id, item_id))
    return len(seen_items) >= USERNAME_ABUSE_ATTEMPT_LIMIT, attempts


def format_duration_arabic(seconds: int) -> str:
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60

    parts = []
    if days:
        parts.append(f"{days} يوم")
    if hours:
        parts.append(f"{hours} ساعة")
    if minutes and not days:
        parts.append(f"{minutes} دقيقة")

    return " و ".join(parts) if parts else "اقل من دقيقة"


def parse_amount(value, default: float = 0) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def save_wallet_to_users_file(user_id: int, wallet: float) -> None:
    users = load_users()
    user = users.setdefault(str(user_id), {})
    user["wallet"] = int(wallet) if float(wallet).is_integer() else wallet
    save_users(users)


def get_user_wallet_from_users_file(user_id: int) -> float:
    users = load_users()
    user = users.get(str(user_id), {})
    return parse_amount(user.get("wallet", 0))


def get_user_wallet(user_id: int) -> float:
    bot_users = load_bot_users()
    bot_user = find_bot_user_entry(bot_users, user_id)
    if bot_user and "amount" in bot_user:
        wallet = parse_amount(bot_user.get("amount"))
        save_wallet_to_users_file(user_id, wallet)
        return wallet

    users = load_users()
    user = users.get(str(user_id), {})
    return parse_amount(user.get("wallet", 0))


def set_user_wallet(user_id: int, wallet: float) -> None:
    save_wallet_to_users_file(user_id, wallet)
    sync_bot_user_amounts(user_id)


def change_user_wallet(user_id: int, amount: float) -> float:
    wallet = get_user_wallet(user_id) + amount
    set_user_wallet(user_id, wallet)
    return wallet


def get_user_display_name(user) -> str:
    if not user:
        return "غير معروف"
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part)
    return full_name or user.username or str(user.id)


def find_bot_user_entry(data: dict, user_id: int) -> dict | None:
    for entry in data.get("users", []):
        if entry.get("id") == user_id:
            return entry
    return None


def sync_bot_user_amounts(user_id: int) -> None:
    data = load_bot_users()
    entry = find_bot_user_entry(data, user_id)
    if not entry:
        return

    entry["amount"] = format_price(get_user_wallet_from_users_file(user_id))
    entry["reserved_amount"] = format_price(get_user_reserved_total(user_id))
    save_bot_users(data)


def register_bot_user(user) -> None:
    if not user:
        return

    data = load_bot_users()
    entry = find_bot_user_entry(data, user.id)
    if not entry:
        entry = {
            "user_number": data["next_number"],
            "name": get_user_display_name(user),
            "username": user.username or "",
            "id": user.id,
            "amount": "0",
            "reserved_amount": "0",
            "first_started_at": int(time.time()),
            "last_started_at": int(time.time()),
        }
        data["users"].append(entry)
        data["next_number"] += 1
    else:
        entry["name"] = get_user_display_name(user)
        entry["username"] = user.username or ""
        entry["last_started_at"] = int(time.time())

    entry["amount"] = format_price(get_user_wallet(user.id))
    entry["reserved_amount"] = format_price(get_user_reserved_total(user.id))
    save_bot_users(data)


def make_short_id() -> str:
    return uuid4().hex[:SHORT_ID_LENGTH]


def load_username_store() -> dict:
    if not os.path.exists(USERNAMES_FILE):
        return {"categories": []}

    with open(USERNAMES_FILE, "r", encoding="utf-8") as usernames_file:
        try:
            store = json.load(usernames_file)
        except json.JSONDecodeError:
            LOGGER.warning("%s is not valid JSON. Starting with an empty store.", USERNAMES_FILE)
            return {"categories": []}

    if not isinstance(store, dict):
        return {"categories": []}
    if not isinstance(store.get("categories"), list):
        store["categories"] = []
    ensure_username_store_ids(store)
    migrate_sold_usernames_to_archive(store)
    return store


def save_username_store(store: dict) -> None:
    safe_save_json(USERNAMES_FILE, store)


def ensure_username_store_ids(store: dict) -> None:
    changed = False

    for category in store.get("categories", []):
        if not category.get("id") or len(str(category.get("id"))) > SHORT_ID_LENGTH:
            category["id"] = make_short_id()
            changed = True

        if not isinstance(category.get("items"), list):
            category["items"] = []
            changed = True

        for item in category.get("items", []):
            if not item.get("id") or len(str(item.get("id"))) > SHORT_ID_LENGTH:
                item["id"] = make_short_id()
                changed = True

    if changed:
        save_username_store(store)


def migrate_sold_usernames_to_archive(store: dict) -> None:
    archive = load_archive()
    changed = False

    for category in store.get("categories", []):
        active_items = []
        for item in category.get("items", []):
            if item.get("status") != "sold":
                active_items.append(item)
                continue

            archive["sold_usernames"].append(
                {
                    "archived_at": int(time.time()),
                    "order_number": item.get("order_number", "غير معروف"),
                    "buyer_id": item.get("sold_to"),
                    "category_id": category.get("id"),
                    "category_name": category.get("name", "بدون اسم"),
                    "item": item,
                }
            )
            changed = True

        category["items"] = active_items

    if changed:
        save_archive(archive)
        save_username_store(store)


def get_username_categories() -> list[dict]:
    return load_username_store().get("categories", [])


def get_username_category(category_id: str) -> dict | None:
    for category in get_username_categories():
        if category.get("id") == category_id:
            category.setdefault("items", [])
            return category
    return None


def get_username_item(category_id: str, item_id: str) -> dict | None:
    category = get_username_category(category_id)
    if not category:
        return None

    for item in category.get("items", []):
        if item.get("id") == item_id:
            return item
    return None


def update_username_category(category_id: str, updated_category: dict) -> bool:
    store = load_username_store()
    for index, category in enumerate(store.get("categories", [])):
        if category.get("id") == category_id:
            store["categories"][index] = updated_category
            save_username_store(store)
            return True
    return False


def delete_username_category(category_id: str) -> dict | None:
    store = load_username_store()
    for index, category in enumerate(store.get("categories", [])):
        if category.get("id") == category_id:
            deleted_category = store["categories"].pop(index)
            save_username_store(store)
            return deleted_category
    return None


def delete_username_item(category_id: str, item_id: str) -> dict | None:
    store = load_username_store()
    deleted_item = None
    for category in store.get("categories", []):
        if category.get("id") != category_id:
            continue
        original_items = category.get("items", [])
        new_items = []
        for item in original_items:
            if item.get("id") == item_id:
                deleted_item = item
                if item.get("status") == "reserved":
                    reservation = item.get("reservation", {})
                    user_id = reservation.get("user_id")
                    deposit = float(reservation.get("deposit", 0))
                    if user_id:
                        change_user_wallet(int(user_id), deposit)
                        sync_bot_user_amounts(int(user_id))
                    
                    reservation_operation = find_user_operation_by_reservation(category_id, item_id)
                    if reservation_operation:
                        update_user_operation(
                            reservation_operation["id"],
                            {"status": "released_by_admin", "released_at": int(time.time())},
                        )
            else:
                new_items.append(item)
        category["items"] = new_items
        break
    save_username_store(store)
    return deleted_item


def format_admin_username_item(category: dict, item: dict) -> str:
    status = item.get("status", "available")
    status_str = "🟢 متاح" if status == "available" else "🟡 محجوز"
    
    lines = [
        "📋 <b>تفاصيل اليوزر (إدارة الآدمن):</b>\n",
        f"• القسم: {category.get('name', 'بدون اسم')}",
        f"• اليوزر: <code>{item.get('name', 'بدون اسم')}</code>",
        f"• السعر: <code>{format_price(get_username_price(item))}</code> ريال",
        f"• الحالة: {status_str}",
    ]
    
    if status == "reserved":
        reservation = item.get("reservation", {})
        user_id = reservation.get("user_id")
        reserved_at = reservation.get("reserved_at")
        expires_at = reservation.get("expires_at")
        lines.append(f"• محجوز بواسطة آيدي: <code>{user_id}</code>")
        lines.append(f"• وقت الحجز: {format_timestamp(reserved_at)}")
        lines.append(f"• وقت انتهاء الحجز: {format_timestamp(expires_at)}")
        
    return "\n".join(lines)


def update_username_item(category_id: str, item_id: str, updated_item: dict) -> bool:
    store = load_username_store()
    for category in store.get("categories", []):
        if category.get("id") != category_id:
            continue
        for index, item in enumerate(category.get("items", [])):
            if item.get("id") == item_id:
                category["items"][index] = updated_item
                save_username_store(store)
                return True
    return False


def release_expired_username_pending_payments(now: int | None = None) -> int:
    store = load_username_store()
    current_time = now or int(time.time())
    released_count = 0

    for category in store.get("categories", []):
        for item in category.get("items", []):
            if item.get("status") != "pending_payment":
                continue
            pending_payment = item.get("pending_payment", {})
            expires_at = int(pending_payment.get("expires_at", 0) or 0)
            created_at = int(pending_payment.get("created_at", 0) or 0)
            if not expires_at and created_at:
                expires_at = created_at + TOPUP_LINK_TTL_SECONDS
            if not expires_at or current_time < expires_at:
                continue

            item["status"] = "available"
            item.pop("pending_payment", None)
            released_count += 1

    if released_count:
        save_username_store(store)

    return released_count


def get_pending_username_payment_items(now: int | None = None) -> list[dict]:
    current_time = now or int(time.time())
    pending_items = []

    for category in get_username_categories():
        for item in category.get("items", []):
            if item.get("status") != "pending_payment":
                continue
            pending_payment = item.get("pending_payment", {})
            expires_at = int(pending_payment.get("expires_at", 0) or 0)
            created_at = int(pending_payment.get("created_at", 0) or 0)
            if not expires_at and created_at:
                expires_at = created_at + TOPUP_LINK_TTL_SECONDS

            pending_items.append(
                {
                    "category_id": category.get("id"),
                    "category_name": category.get("name", "بدون اسم"),
                    "item_id": item.get("id"),
                    "item_name": item.get("name", "يوزر بدون اسم"),
                    "user_id": pending_payment.get("user_id"),
                    "payment_id": pending_payment.get("payment_id"),
                    "created_at": created_at,
                    "expires_at": expires_at,
                    "remaining_seconds": max(expires_at - current_time, 0) if expires_at else 0,
                }
            )

    return pending_items


def archive_sold_username(
    category_id: str,
    item_id: str,
    sold_item: dict,
    order_number: str,
    buyer_id: int,
) -> bool:
    store = load_username_store()
    archived = False
    category_name = "بدون اسم"

    for category in store.get("categories", []):
        if category.get("id") != category_id:
            continue

        category_name = category.get("name", "بدون اسم")
        original_items = category.get("items", [])
        category["items"] = [
            item for item in original_items if item.get("id") != item_id
        ]
        archived = len(category["items"]) != len(original_items)
        break

    if not archived:
        return False

    archive = load_archive()
    archive["sold_usernames"].append(
        {
            "archived_at": int(time.time()),
            "order_number": order_number,
            "buyer_id": buyer_id,
            "category_id": category_id,
            "category_name": category_name,
            "item": sold_item,
        }
    )
    save_archive(archive)
    save_username_store(store)
    return True


def get_username_price(item: dict) -> float:
    try:
        return float(item.get("price", 0))
    except (TypeError, ValueError):
        return 0


def get_reservation_deposit(price: float) -> float:
    return round(price / 3, 2)


def get_user_reserved_total(user_id: int) -> float:
    total = 0.0
    for category in get_username_categories():
        for item in category.get("items", []):
            if item.get("status") != "reserved":
                continue
            reservation = item.get("reservation", {})
            if reservation.get("user_id") == user_id:
                total += float(reservation.get("deposit", 0))
    return total


def get_active_user_reservation(user_id: int) -> tuple[str, str, dict] | None:
    for category in get_username_categories():
        for item in category.get("items", []):
            if item.get("status") != "reserved":
                continue
            reservation = item.get("reservation", {})
            if reservation.get("user_id") == user_id:
                return category["id"], item["id"], item
    return None


def get_active_user_reservations(user_id: int) -> list[tuple[str, str, dict, dict]]:
    reservations = []
    for category in get_username_categories():
        for item in category.get("items", []):
            if item.get("status") != "reserved":
                continue
            reservation = item.get("reservation", {})
            if reservation.get("user_id") == user_id:
                reservations.append((category["id"], item["id"], item, reservation))
    return reservations


def ensure_product_ids(products: list[dict]) -> list[dict]:
    changed = False
    for product in products:
        if not product.get("id"):
            product["id"] = uuid4().hex
            changed = True

    if changed:
        save_products(products)

    return products


def get_product(product_id: str) -> dict | None:
    products = ensure_product_ids(load_products())
    for product in products:
        if product.get("id") == product_id:
            return product

    return None


def update_product(product_id: str, updated_product: dict) -> bool:
    products = ensure_product_ids(load_products())
    for index, product in enumerate(products):
        if product.get("id") == product_id:
            products[index] = updated_product
            save_products(products)
            return True

    return False


def delete_product(product_id: str) -> dict | None:
    products = ensure_product_ids(load_products())
    for index, product in enumerate(products):
        if product.get("id") == product_id:
            deleted_product = products.pop(index)
            save_products(products)
            return deleted_product
    return None


def get_delivery_items(product: dict) -> list[dict]:
    delivery_items = product.get("delivery_items")
    if isinstance(delivery_items, list):
        return delivery_items

    old_delivery = product.get("delivery")
    return [old_delivery] if isinstance(old_delivery, dict) else []


def get_product_price(product: dict) -> float:
    try:
        return float(product.get("price", 0))
    except (TypeError, ValueError):
        return 0


def format_price(price: float) -> str:
    return str(int(price)) if float(price).is_integer() else str(price)


def calculate_net_tap(amount: float) -> float:
    if amount <= 0:
        return 0.0
    fee = (amount * 0.03) + 1.00
    vat = fee * 0.15
    total_fee = fee + vat
    net = amount - total_fee
    return max(0.0, round(net, 2))


def get_active_payment_remaining_time(user_id: int) -> int | None:
    now = int(time.time())
    for topup in load_topups().get("topups", []):
        if topup.get("user_id") == user_id:
            if topup.get("credited"):
                continue
            status = str(topup.get("payment_status") or "").lower()
            if status in ("expired", "captured", "failed", "cancelled", "voided"):
                continue
            created_at = int(topup.get("created_at", 0))
            elapsed = now - created_at
            if elapsed < 20 * 60:
                return 20 * 60 - elapsed
    return None


def format_remaining_time_arabic(seconds: int) -> str:
    mins = seconds // 60
    secs = seconds % 60
    parts = []
    if mins > 0:
        if mins == 1:
            parts.append("دقيقة واحدة")
        elif mins == 2:
            parts.append("دقيقتين")
        elif 3 <= mins <= 10:
            parts.append(f"{mins} دقائق")
        else:
            parts.append(f"{mins} دقيقة")
    if secs > 0:
        if secs == 1:
            parts.append("ثانية واحدة")
        elif secs == 2:
            parts.append("ثانيتين")
        elif 3 <= secs <= 10:
            parts.append(f"{secs} ثوانٍ")
        else:
            parts.append(f"{secs} ثانية")
    return " و ".join(parts)




def format_timestamp(timestamp: int | float | None) -> str:
    if not timestamp:
        return "غير معروف"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(timestamp)))


def format_date(timestamp: int | float | None) -> str:
    if not timestamp:
        return "غير معروف"
    return time.strftime("%Y-%m-%d", time.localtime(float(timestamp)))


def build_support_message(message, sender: dict) -> dict | None:
    base = {
        "id": make_short_id(),
        "sender": sender,
        "created_at": int(time.time()),
    }
    if message.text:
        base.update({"type": "text", "text": message.text})
        return base
    if message.photo:
        photo = message.photo[-1]
        base.update({"type": "photo", "file_id": photo.file_id, "caption": message.caption or ""})
        return base
    if message.document:
        base.update(
            {
                "type": "document",
                "file_id": message.document.file_id,
                "file_name": message.document.file_name,
                "caption": message.caption or "",
            }
        )
        return base
    if message.video:
        base.update(
            {
                "type": "video",
                "file_id": message.video.file_id,
                "file_name": message.video.file_name,
                "caption": message.caption or "",
            }
        )
        return base
    return None


def support_message_preview(message: dict) -> str:
    sender = message.get("sender", {})
    role = "الدعم" if sender.get("role") in {"admin", "employee"} else "العميل"
    created_at = format_timestamp(message.get("created_at"))
    message_type = message.get("type")
    if message_type == "text":
        content = message.get("text", "")
    elif message_type == "photo":
        content = "🖼️ صورة"
        if message.get("caption"):
            content += f" - {message.get('caption')}"
    elif message_type == "document":
        content = f"📎 ملف: {message.get('file_name', 'بدون اسم')}"
        if message.get("caption"):
            content += f" - {message.get('caption')}"
    elif message_type == "video":
        content = f"🎥 فيديو: {message.get('file_name', 'بدون اسم')}"
        if message.get("caption"):
            content += f" - {message.get('caption')}"
    else:
        content = "رسالة غير معروفة"
    return f"{role} - {created_at}\n{content}"


def format_ticket(ticket: dict, for_staff: bool = False) -> str:
    status = "مغلقة ✅" if ticket.get("status") == "closed" else "مفتوحة ⏳"
    lines = [
        "🎫 تفاصيل التذكرة.",
        "",
        f"🔖 رقم التذكرة: {ticket.get('number', ticket.get('id'))}",
        f"📌 الحالة: {status}",
        f"🏷️ النوع: {ticket.get('category_label', 'دعم')}",
        f"📅 تاريخ الفتح: {format_timestamp(ticket.get('created_at'))}",
    ]
    if for_staff:
        username = f"@{ticket.get('username')}" if ticket.get("username") else "لا يوجد"
        lines.extend(
            [
                "",
                "👤 معلومات العميل:",
                f"الاسم: {ticket.get('user_name', 'غير معروف')}",
                f"اليوزر: {username}",
                f"الايدي: {ticket.get('user_id')}",
            ]
        )

    messages = ticket.get("messages", [])
    lines.extend(["", "💬 آخر الرسائل:"])
    if not messages:
        lines.append("لا توجد رسائل.")
    else:
        for message in messages[-5:]:
            lines.append(support_message_preview(message))
            lines.append("----------")

    return "\n".join(lines).strip("-\n")


def status_icon(status: str | None, credited: bool | None = None) -> str:
    normalized = str(status or "").lower()
    if credited is True:
        return "✅"
    if credited is False:
        if normalized in {"failed", "declined", "cancelled", "canceled", "expired", "refunded"}:
            return "❌"
        return "⏳"
    if normalized in {"completed", "finished", "confirmed", "sending", "captured", "paid"}:
        return "✅"
    if normalized in {"failed", "declined", "cancelled", "canceled", "expired", "refunded"}:
        return "❌"
    return "⏳"


def get_user_topups(user_id: int) -> list[dict]:
    return [
        topup
        for topup in load_topups().get("topups", [])
        if topup.get("user_id") == user_id
    ]


def format_purchase_line(operation: dict) -> str:
    icon = status_icon(operation.get("status"))
    item_name = operation.get("item_name", "منتج بدون اسم")
    amount = format_price(parse_amount(operation.get("amount", 0)))
    return rtl_text(f"{icon} - {item_name} - {amount} ريال")


def format_topup_line(topup: dict) -> str:
    icon = status_icon(topup.get("payment_status"), bool(topup.get("credited")))
    amount = format_price(parse_amount(topup.get("credit_amount", topup.get("amount", 0))))
    date = format_date(topup.get("credited_at") or topup.get("created_at"))
    return rtl_text(f"{icon} - {amount} ريال - {date}")


def format_purchases_and_topups(user_id: int) -> str:
    purchases = get_user_purchase_operations(user_id)

    lines = ["🧾 العمليات.", "", "🛒 المشتريات:"]
    if purchases:
        lines.extend(format_purchase_line(operation) for operation in reversed(purchases[-5:]))
    else:
        lines.append("📭 لا توجد مشتريات حتى الان.")

    return "\n".join(lines)


def format_active_reservations(user_id: int) -> str:
    reservations = get_active_user_reservations(user_id)
    if not reservations:
        return "⏳ الحجوزات.\n\nلا توجد حجوزات حالية."

    lines = ["⏳ الحجوزات الحالية.\n"]
    for category_id, item_id, item, reservation in reservations:
        deposit = format_price(parse_amount(reservation.get("deposit", 0)))
        reserved_at = format_date(reservation.get("reserved_at"))
        expires_at = format_date(reservation.get("expires_at"))
        can_cancel = can_cancel_reservation(reservation)
        action_note = "شراء او الغاء الحجز" if can_cancel else "شراء فقط"
        lines.append(
            rtl_text(
                f"⏳ - {item.get('name', 'يوزر بدون اسم')} - {deposit} ريال\n"
                f"تاريخ الحجز: {reserved_at}\n"
                f"ينتهي الحجز: {expires_at}\n"
                f"الاجراء المتاح: {action_note}"
            )
        )

    return "\n\n".join(lines)


def format_user_operations(user_id: int, view: str = "all") -> str:
    if view == "all":
        return format_purchases_and_topups(user_id)
    if view == "reservations":
        return format_active_reservations(user_id)

    data = load_user_operations()
    allowed_types = {
        "purchases": {"purchase"},
        "reservations": {"reservation"},
        "all": {"purchase", "reservation"},
    }.get(view, {"purchase", "reservation"})
    user_operations = [
        operation
        for operation in data.get("operations", [])
        if operation.get("user_id") == user_id and operation.get("type") in allowed_types
    ]

    if not user_operations:
        empty_titles = {
            "purchases": "المشتريات",
            "reservations": "الحجوزات",
            "all": "العمليات",
        }
        title = empty_titles.get(view, "العمليات")
        icons = {
            "purchases": "🛒",
            "reservations": "⏳",
            "all": "🧾",
        }
        return f"{icons.get(view, '🧾')} {title}.\n\nلا توجد بيانات حتى الان."

    titles = {
        "purchases": "🛒 المشتريات.",
        "reservations": "⏳ الحجوزات.",
        "all": "🧾 العمليات.",
    }
    lines = [f"{titles.get(view, 'العمليات.')}\n"]
    hidden_count = 0
    for operation in reversed(user_operations):
        operation_type = operation.get("type")
        status = operation.get("status", "غير معروف")
        item_name = operation.get("item_name", "عنصر بدون اسم")
        amount = format_price(parse_amount(operation.get("amount", 0)))
        created_at = format_timestamp(operation.get("created_at"))

        if operation_type == "purchase":
            block = (
                f"رقم الطلب: {operation.get('order_number', 'غير متوفر')}\n"
                f"النوع: شراء\n"
                f"الحالة: مكتمل\n"
                f"العنصر: {item_name}\n"
                f"المبلغ: {amount} ريال\n"
                f"التاريخ: {created_at}"
            )
        elif operation_type == "reservation":
            expires_at = format_timestamp(operation.get("expires_at"))
            action_note = ""
            if status == "active":
                details = operation.get("details", {})
                item = get_username_item(details.get("category_id"), details.get("item_id"))
                if item and item.get("status") == "reserved":
                    can_cancel = can_cancel_reservation(item.get("reservation", {}))
                    action_note = (
                        "\nالاجراء المتاح: شراء او الغاء الحجز"
                        if can_cancel
                        else "\nالاجراء المتاح: شراء فقط، وانتهت مدة الغاء الحجز"
                    )
            block = (
                f"النوع: حجز\n"
                f"الحالة: {status}\n"
                f"العنصر: {item_name}\n"
                f"المبلغ المحجوز: {amount} ريال\n"
                f"تاريخ الحجز: {created_at}\n"
                f"ينتهي الحجز: {expires_at}"
                f"{action_note}"
            )
        else:
            continue

        candidate = "\n\n".join(lines + [block])
        if len(candidate) > 3600:
            hidden_count += 1
            continue
        lines.append(block)

    if hidden_count:
        lines.append(f"\nتم اخفاء {hidden_count} عملية قديمة بسبب حد طول رسالة تليجرام.")

    return "\n\n".join(lines)


def get_archived_username_by_order(order_number: str, user_id: int) -> dict | None:
    if not order_number:
        return None

    for archived in load_archive().get("sold_usernames", []):
        if (
            str(archived.get("order_number") or "") == str(order_number)
            and archived.get("buyer_id") == user_id
        ):
            return archived.get("item") if isinstance(archived.get("item"), dict) else None

    return None


def get_purchase_delivery_item(operation: dict) -> dict | None:
    details = operation.get("details") if isinstance(operation.get("details"), dict) else {}
    delivery = details.get("delivery")
    if isinstance(delivery, dict):
        return delivery

    if operation.get("item_type") == "username":
        archived_item = get_archived_username_by_order(
            str(operation.get("order_number") or ""),
            int(operation.get("user_id", 0)),
        )
        if archived_item and isinstance(archived_item.get("delivery"), dict):
            return archived_item["delivery"]

    return None


def format_purchase_details(operation: dict) -> str:
    details = operation.get("details") if isinstance(operation.get("details"), dict) else {}
    delivery = get_purchase_delivery_item(operation)
    delivery_type = delivery.get("type") if isinstance(delivery, dict) else None
    if delivery_type == "text":
        delivery_status = "✅ مرفق داخل هذه الرسالة"
    elif delivery:
        delivery_status = "✅ سيتم ارساله في رسالة منفصلة"
    else:
        delivery_status = "❌ غير محفوظ لهذه العملية"

    lines = [
        "📋 تفاصيل العملية.",
        "",
        "🛒 معلومات الشراء:",
        f"🔖 رقم الطلب: {operation.get('order_number', 'غير متوفر')}",
        f"📅 تاريخ الشراء: {format_date(operation.get('created_at'))}",
        f"💰 السعر: {format_price(parse_amount(operation.get('amount', 0)))} ريال",
        f"📦 اسم المنتج: {operation.get('item_name', 'منتج بدون اسم')}",
        "",
        "🚚 معلومات التسليم:",
        f"📌 حالة التسليم: {delivery_status}",
    ]

    if delivery_type == "text":
        lines.extend(
            [
                "",
                "📨 التسليم:",
                "----------",
                delivery.get("text", ""),
                "----------",
            ]
        )

    if details.get("deposit") is not None:
        lines.append(f"العربون المدفوع: {format_price(parse_amount(details.get('deposit', 0)))} ريال")
    if details.get("remaining_paid") is not None:
        lines.append(f"المبلغ المتبقي المدفوع: {format_price(parse_amount(details.get('remaining_paid', 0)))} ريال")

    return "\n".join(lines)


def format_purchase_delivery_caption(operation: dict) -> str:
    return (
        f"📅 تاريخ الشراء: {format_date(operation.get('created_at'))}\n"
        f"🔖 رقم الطلب: {operation.get('order_number', 'غير متوفر')}\n"
        f"💰 السعر: {format_price(parse_amount(operation.get('amount', 0)))} ريال"
    )


def format_products_menu() -> tuple[str, InlineKeyboardMarkup]:
    products = ensure_product_ids(load_products())
    if not products:
        return "📦 قسم المنتجات الرقمية.\n\nلا توجد منتجات متاحة حاليا.", back_keyboard()

    return "📦 قسم المنتجات الرقمية.\n\nاختر المنتج الذي تريد شراءه:", products_keyboard(products)


def format_product_purchase(product: dict) -> str:
    description = product.get("description") or "لا يوجد وصف"
    quantity = len(get_delivery_items(product))
    price = format_price(get_product_price(product))
    return (
        "📋 تفاصيل المنتج.\n\n"
        f"📦 اسم المنتج: {product.get('name', 'منتج بدون اسم')}\n"
        f"📝 الوصف: {description}\n"
        f"💰 السعر: {price} ريال\n"
        f"📊 الكمية المتوفرة: {quantity}"
    )


def format_products() -> str:
    products = ensure_product_ids(load_products())
    if not products:
        return "📦 قسم المنتجات الرقمية.\n\nلا توجد منتجات متاحة حاليا."

    lines = ["📦 قسم المنتجات الرقمية.\n"]
    for index, product in enumerate(products, start=1):
        description = product.get("description") or "لا يوجد وصف"
        quantity = len(get_delivery_items(product))
        price = format_price(get_product_price(product))
        lines.append(
            f"{index}. {product.get('name', 'منتج بدون اسم')}\n"
            f"📝 الوصف: {description}\n"
            f"💰 السعر: {price} ريال\n"
            f"📊 الكمية المتوفرة: {quantity}"
        )

    return "\n\n".join(lines)


def format_admin_products() -> tuple[str, InlineKeyboardMarkup]:
    products = ensure_product_ids(load_products())
    if not products:
        return (
            "📭 لا توجد منتجات حاليا.\n\n"
            "➕ اضف منتج جديد من لوحة الادمن.",
            back_to_admin_menu_keyboard(),
        )

    lines = ["📋 المنتجات المتوفرة.\n\nاختر منتج لادارة التسليم التلقائي:"]
    return "\n".join(lines), products_admin_keyboard(products)


def format_admin_statistics() -> str:
    # 1. Members stats
    bot_users = load_bot_users().get("users", [])
    total_users = len(bot_users)
    
    current_time = time.time()
    active_24h = sum(1 for u in bot_users if u.get("last_started_at", 0) >= current_time - 86400)
    active_7d = sum(1 for u in bot_users if u.get("last_started_at", 0) >= current_time - 86400 * 7)
    
    # 2. Wallets stats
    users_data = load_users()
    total_balances = sum(float(info.get("wallet", 0)) for info in users_data.values() if isinstance(info, dict))
    
    # 3. Sales stats (with reset support)
    settings = load_bot_settings()
    sales_stats_reset_time = settings.get("sales_stats_reset_time", 0)
    
    operations = load_user_operations().get("operations", [])
    purchases = [
        op for op in operations 
        if op.get("type") == "purchase" 
        and op.get("status") == "completed"
        and op.get("created_at", 0) >= sales_stats_reset_time
    ]
    
    total_sales_count = len(purchases)
    total_sales_revenue = sum(float(op.get("amount", 0)) for op in purchases)
    
    username_purchases = [op for op in purchases if op.get("item_type") == "username"]
    username_sales_count = len(username_purchases)
    username_sales_revenue = sum(float(op.get("amount", 0)) for op in username_purchases)
    
    product_purchases = [op for op in purchases if op.get("item_type") == "digital_product"]
    product_sales_count = len(product_purchases)
    product_sales_revenue = sum(float(op.get("amount", 0)) for op in product_purchases)
    
    sales_24h = [op for op in purchases if op.get("created_at", 0) >= current_time - 86400]
    sales_count_24h = len(sales_24h)
    sales_revenue_24h = sum(float(op.get("amount", 0)) for op in sales_24h)
    
    # 4. Stock stats
    # Products stock
    products = load_products()
    available_digital_products = sum(len(get_delivery_items(p)) for p in products)
    
    # Usernames stock
    categories = get_username_categories()
    available_usernames = sum(
        1 for cat in categories 
        for item in cat.get("items", []) 
        if item.get("status") == "available"
    )
    
    # 5. Support tickets stats
    tickets_data = load_support_tickets().get("tickets", [])
    open_tickets = sum(1 for t in tickets_data if t.get("status") != "closed")
    
    # Format message in Arabic using HTML
    text = (
        "📊 <b>إحصائيات المتجر الشاملة</b> 📊\n\n"
        "👥 <b>إحصائيات الأعضاء:</b>\n"
        f"• إجمالي الأعضاء: <code>{total_users}</code> عضو\n"
        f"• النشطين خلال 24 ساعة: <code>{active_24h}</code>\n"
        f"• النشطين خلال 7 أيام: <code>{active_7d}</code>\n"
        f"• إجمالي أرصدة الأعضاء: <code>{format_price(total_balances)}</code> ريال\n\n"
        
        "🛍️ <b>إحصائيات المبيعات:</b>\n"
        f"• إجمالي المبيعات المكتملة: <code>{total_sales_count}</code> طلب\n"
        f"• إجمالي إيرادات المبيعات: <code>{format_price(total_sales_revenue)}</code> ريال\n"
        f"  - مبيعات اليوزرات: <code>{username_sales_count}</code> طلب (<code>{format_price(calculate_net_tap(username_sales_revenue))}</code> ريال)\n"
        f"  - مبيعات المنتجات: <code>{product_sales_count}</code> طلب (<code>{format_price(calculate_net_tap(product_sales_revenue))}</code> ريال)\n"
        f"• المبيعات خلال 24 ساعة: <code>{sales_count_24h}</code> طلب (<code>{format_price(calculate_net_tap(sales_revenue_24h))}</code> ريال)\n\n"
        
        "📦 <b>إحصائيات المخزون المتوفر:</b>\n"
        f"• المنتجات الرقمية المتوفرة: <code>{available_digital_products}</code> قطعة/حساب\n"
        f"• اليوزرات المتوفرة للبيع: <code>{available_usernames}</code> يوزر\n\n"
        
        "🎫 <b>الدعم الفني:</b>\n"
        f"• تذاكر الدعم المفتوحة حالياً: <code>{open_tickets}</code> تذكرة"
    )
    
    # 6. Admin / Staff statistics
    staff_ops = load_staff_operations().get("operations", [])
    filtered_staff_ops = [
        op for op in staff_ops
        if op.get("created_at", 0) >= sales_stats_reset_time
    ]
    
    staff_stats = {}
    products_by_id = {p["id"]: p for p in load_products()}
    
    # Initialize admins
    for admin_id in get_admin_ids():
        info = get_known_user_info(admin_id)
        name = info.get("name") or "آدمن"
        username = info.get("username", "")
        staff_stats[admin_id] = {
            "name": name,
            "username": username,
            "role": "admin",
            "usernames_count": 0,
            "usernames_amount": 0.0,
            "products_count": 0,
            "products_amount": 0.0
        }
        
    # Initialize employees
    for employee in load_employees().get("employees", []):
        try:
            emp_id = int(employee.get("id"))
        except (ValueError, TypeError):
            continue
        staff_stats[emp_id] = {
            "name": employee.get("name") or "موظف",
            "username": employee.get("username", ""),
            "role": "employee",
            "usernames_count": 0,
            "usernames_amount": 0.0,
            "products_count": 0,
            "products_amount": 0.0
        }
        
    for op in filtered_staff_ops:
        actor = op.get("actor")
        if not actor or not actor.get("id"):
            continue
        try:
            actor_id = int(actor["id"])
        except (ValueError, TypeError):
            continue
        
        if actor_id not in staff_stats:
            staff_stats[actor_id] = {
                "name": actor.get("name") or actor.get("username") or str(actor_id),
                "username": actor.get("username", ""),
                "role": actor.get("role", "staff"),
                "usernames_count": 0,
                "usernames_amount": 0.0,
                "products_count": 0,
                "products_amount": 0.0
            }
            
        stats_entry = staff_stats[actor_id]
        if actor.get("name"):
            stats_entry["name"] = actor["name"]
        if actor.get("username"):
            stats_entry["username"] = actor["username"]
            
        action = op.get("action")
        target = op.get("target", {})
        
        if action == "add_username":
            price = float(target.get("price", 0))
            stats_entry["usernames_count"] += 1
            stats_entry["usernames_amount"] += price
        elif action == "add_product_stock":
            price = float(target.get("price", 0))
            if price == 0 and "product_id" in target:
                p_id = target["product_id"]
                if p_id in products_by_id:
                    price = float(products_by_id[p_id].get("price", 0))
            stats_entry["products_count"] += 1
            stats_entry["products_amount"] += price

    staff_lines = []
    for staff_id, s in staff_stats.items():
        role_icon = "👑" if s.get("role") == "admin" else "👨‍💼"
        display_name = s["name"]
        if s["username"]:
            display_name += f" (@{s['username']})"
            
        u_count = s["usernames_count"]
        u_amount = format_price(calculate_net_tap(s["usernames_amount"]))
        p_count = s["products_count"]
        p_amount = format_price(calculate_net_tap(s["products_amount"]))
        
        staff_lines.append(
            f"{role_icon} <b>{display_name}:</b>\n"
            f"  - اليوزرات المضافة: <code>{u_count}</code> (<code>{u_amount}</code> ريال)\n"
            f"  - المنتجات المضافة: <code>{p_count}</code> (<code>{p_amount}</code> ريال)"
        )
        
    if staff_lines:
        text += "\n\n👮 <b>إحصائيات الإدارة والمشرفين:</b>\n" + "\n".join(staff_lines)

    if sales_stats_reset_time > 0:
        text += f"\n\n⚠️ <i>ملاحظة: تم تصفير إحصائيات المبيعات بتاريخ {format_timestamp(sales_stats_reset_time)}</i>"
        
    return text


def format_product_details(product: dict) -> str:
    description = product.get("description") or "لا يوجد وصف"
    quantity = len(get_delivery_items(product))
    delivery_status = "مضاف" if quantity else "غير مضاف"
    price = format_price(get_product_price(product))

    return (
        "📋 تفاصيل المنتج.\n\n"
        f"📦 اسم المنتج: {product.get('name', 'منتج بدون اسم')}\n"
        f"📝 الوصف: {description}\n"
        f"💰 السعر: {price} ريال\n"
        f"🚚 التسليم التلقائي: {delivery_status}\n"
        f"📊 الكمية المتوفرة: {quantity}"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_bot_user(update.effective_user)
    user = update.effective_user
    if user and is_user_banned(user.id) and not (is_admin(update) or is_employee(update)):
        await update.message.reply_text("🚫 حسابك محظور من استخدام البوت.")
        return
    if not await ensure_required_channel_subscription(update, context):
        return

    await update.message.reply_text(
        WELCOME_MESSAGE,
        reply_markup=main_menu_keyboard(
            show_admin=is_admin(update),
            show_employee=is_employee(update),
        ),
    )


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user and is_user_banned(user.id) and not is_admin(update):
        await update.message.reply_text("🚫 حسابك محظور من استخدام البوت.")
        return
    if not is_admin(update):
        await update.message.reply_text(
            "🔒 هذه القائمة مخصصة للادمن فقط.\n\n"
            f"🆔 معرف حسابك هو: {user.id if user else 'غير معروف'}"
        )
        return

    await update.message.reply_text(
        "🛠️ لوحة الادمن.\n\n"
        "👇 اختر العملية التي تريد تنفيذها:",
        reply_markup=admin_keyboard(),
    )


async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if not is_admin(update):
        await edit_message(query, "🔒 هذه العملية مخصصة للادمن فقط.")
        return ConversationHandler.END

    await edit_message(
        query,
        "📢 <b>بدء الإذاعة الشاملة</b>\n\n"
        "ارسل الرسالة التي تريد إرسالها إلى جميع مستخدمي البوت.\n"
        "يمكنك إرسال نص، صورة، مستند، أو فيديو.\n"
        "عند الإرسال، سيقوم البوت بإرسالها للجميع تلقائياً.\n\n"
        "اضغط /cancel أو الزر أدناه للإلغاء.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ الغاء", callback_data="cancel_broadcast")]]
        ),
        parse_mode="HTML"
    )
    return BROADCAST_MESSAGE


async def receive_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update):
        await update.message.reply_text("🔒 هذه العملية مخصصة للادمن فقط.")
        return ConversationHandler.END

    message = update.message
    bot_users = load_bot_users().get("users", [])
    user_ids = list(set([u["id"] for u in bot_users if "id" in u]))

    if not user_ids:
        await message.reply_text("❌ لا يوجد مستخدمين لإرسال الإذاعة لهم.")
        return ConversationHandler.END

    status_message = await message.reply_text(
        f"⏳ جاري إرسال الإذاعة إلى {len(user_ids)} مستخدم..."
    )

    success_count = 0
    fail_count = 0

    for user_id in user_ids:
        try:
            await context.bot.copy_message(
                chat_id=int(user_id),
                from_chat_id=message.chat_id,
                message_id=message.message_id
            )
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail_count += 1

    await status_message.edit_text(
        "📢 <b>تم اكتمال الإذاعة الشاملة</b>\n\n"
        f"✅ تم الإرسال بنجاح إلى: <code>{success_count}</code> مستخدم\n"
        f"❌ فشل الإرسال إلى: <code>{fail_count}</code> مستخدم",
        parse_mode="HTML"
    )
    return ConversationHandler.END


async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await edit_message(query, "❌ تم إلغاء الإذاعة.", reply_markup=back_to_admin_menu_keyboard())
    else:
        await update.message.reply_text("❌ تم إلغاء الإذاعة.", reply_markup=back_to_admin_menu_keyboard())

    return ConversationHandler.END


PAYMENT_SETTING_LABELS = {
    "NOWPAYMENTS_API_KEY": "NOWPayments API Key",
    "NOWPAYMENTS_EMAIL": "NOWPayments Email",
    "NOWPAYMENTS_PASSWORD": "NOWPayments Password",
    "TAP_SECRET_KEY": "Tap Secret Key (مثال: sk_live_...)",
    "TOPUP_CREDIT_RATE": "معدل شحن الرصيد (Topup Rate)",
}


async def start_edit_payment_setting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if not is_admin(update):
        await edit_message(query, "🔒 هذه العملية مخصصة للادمن فقط.")
        return ConversationHandler.END

    setting_key = query.data.split(":", 1)[1]
    context.user_data["editing_payment_setting_key"] = setting_key
    label = PAYMENT_SETTING_LABELS.get(setting_key, setting_key)

    await edit_message(
        query,
        f"✏️ <b>تعديل إعداد: {label}</b>\n\n"
        "يرجى إرسال القيمة الجديدة الآن في الشات:\n\n"
        "💡 <i>(أرسل القيمة كرسالة نصية)</i>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩️ إلغاء", callback_data="cancel_edit_payment_setting")]
        ]),
        parse_mode="HTML",
    )
    return PAYMENT_SETTING_INPUT


async def receive_payment_setting_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update):
        return ConversationHandler.END

    setting_key = context.user_data.pop("editing_payment_setting_key", None)
    if not setting_key:
        await update.message.reply_text("⚠️ حدث خطأ أو انتهت الجلسة.", reply_markup=back_to_admin_menu_keyboard())
        return ConversationHandler.END

    new_value = update.message.text.strip()
    save_payment_setting(setting_key, new_value)
    label = PAYMENT_SETTING_LABELS.get(setting_key, setting_key)

    parent_menu = "nowpayments" if setting_key.startswith("NOWPAYMENTS_") else ("tap" if setting_key.startswith("TAP_") else "main")

    if parent_menu == "nowpayments":
        markup = admin_nowpayments_keyboard()
        text = f"✅ تم تحديث <b>{label}</b> بنجاح!\n\n" + format_nowpayments_settings()
    elif parent_menu == "tap":
        markup = admin_tap_keyboard()
        text = f"✅ تم تحديث <b>{label}</b> بنجاح!\n\n" + format_tap_settings()
    else:
        markup = admin_payment_settings_keyboard()
        text = f"✅ تم تحديث <b>{label}</b> بنجاح!\n\n" + format_payment_settings_overview()

    await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")
    return ConversationHandler.END


async def cancel_edit_payment_setting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        context.user_data.pop("editing_payment_setting_key", None)
        await edit_message(
            query,
            "❌ تم إلغاء التعديل.\n\n" + format_payment_settings_overview(),
            reply_markup=admin_payment_settings_keyboard(),
            parse_mode="HTML",
        )
    else:
        context.user_data.pop("editing_payment_setting_key", None)
        await update.message.reply_text(
            "❌ تم إلغاء التعديل.\n\n" + format_payment_settings_overview(),
            reply_markup=admin_payment_settings_keyboard(),
            parse_mode="HTML",
        )
    return ConversationHandler.END


async def start_set_required_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if not is_admin(update):
        await edit_message(query, "🔒 هذه العملية مخصصة للادمن فقط.")
        return ConversationHandler.END

    await edit_message(
        query,
        "📢 تحديد قناة الاشتراك الاجباري.\n\n"
        "ارسل معرف القناة مثل @channelname او رابطها t.me/channelname.\n"
        "اذا كانت القناة خاصة ارسل ايدي القناة، لكن زر الدخول لن يظهر بدون رابط عام.\n\n"
        "مهم: لازم تضيف البوت مشرف في القناة حتى يقدر يتحقق من الاشتراك.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ الغاء", callback_data="cancel_required_channel")]]
        ),
    )
    return REQUIRED_CHANNEL


async def receive_required_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update):
        await update.message.reply_text("🔒 هذه العملية مخصصة للادمن فقط.")
        return ConversationHandler.END

    channel = normalize_required_channel(update.message.text)
    if not channel:
        await update.message.reply_text("صيغة القناة غير صحيحة. ارسل @channelname او رابط t.me/channelname:")
        return REQUIRED_CHANNEL

    settings = load_bot_settings()
    settings["required_channel"] = channel
    save_bot_settings(settings)

    await update.message.reply_text(
        "✅ تم تفعيل الاشتراك الاجباري.\n\n"
        "تأكد أن البوت مشرف في القناة حتى يقدر يتحقق من اشتراك العملاء.",
        reply_markup=required_channel_admin_keyboard(),
    )
    return ConversationHandler.END


async def cancel_required_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await edit_message(
            query,
            "✅ تم الغاء تعديل قناة الاشتراك.",
            reply_markup=required_channel_admin_keyboard(),
        )
    else:
        await update.message.reply_text(
            "✅ تم الغاء تعديل قناة الاشتراك.",
            reply_markup=required_channel_admin_keyboard(),
        )
    return ConversationHandler.END


async def start_add_employee(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if not is_admin(update):
        await edit_message(query, "🔒 هذه العملية مخصصة للادمن فقط.")
        return ConversationHandler.END

    await edit_message(
        query,
        "👨‍💼 توظيف موظف جديد.\n\n"
        "🆔 ارسل ايدي حساب الموظف في تليجرام:",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ الغاء", callback_data="cancel_add_employee")]]
        ),
    )
    return EMPLOYEE_ID


async def receive_employee_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update):
        await update.message.reply_text("🔒 هذه العملية مخصصة للادمن فقط.")
        return ConversationHandler.END

    raw_employee_id = update.message.text.strip()
    try:
        employee_id = int(raw_employee_id)
    except ValueError:
        await update.message.reply_text("الايدي لازم يكون رقم. ارسل ايدي الموظف:")
        return EMPLOYEE_ID

    data = load_employees()
    for employee in data.get("employees", []):
        if employee.get("id") == employee_id:
            await update.message.reply_text(
                "هذا الموظف موجود مسبقا.",
                reply_markup=admin_employees_keyboard(),
            )
            return ConversationHandler.END

    known_info = get_known_user_info(employee_id)
    data.setdefault("employees", []).append(
        {
            "id": employee_id,
            "name": known_info["name"],
            "username": known_info["username"],
            "added_by": update.effective_user.id,
            "added_at": int(time.time()),
        }
    )
    save_employees(data)

    await update.message.reply_text(
        "✅ تم توظيف الموظف بنجاح.\n\n"
        f"ايدي الموظف: {employee_id}",
        reply_markup=admin_employees_keyboard(),
    )
    return ConversationHandler.END


async def cancel_add_employee(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await edit_message(query, "✅ تم الغاء التوظيف.", reply_markup=admin_employees_keyboard())
    else:
        await update.message.reply_text("✅ تم الغاء التوظيف.", reply_markup=admin_employees_keyboard())

    return ConversationHandler.END


async def start_topup_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if not await ensure_required_channel_subscription(update, context):
        return ConversationHandler.END

    if not update.effective_user:
        await edit_message(query, "⚠️ تعذر معرفة المستخدم. حاول مرة اخرى.")
        return ConversationHandler.END

    topup_method = query.data.split(":", 1)[1]
    context.user_data["topup_method"] = topup_method
    method_names = {
        "nowpayments": "NOWPayments",
        "tap": "Tap Payments",
    }
    method_name = method_names.get(topup_method, "بوابة الدفع")
    await edit_message(
        query,
        f"إضافة أموال عبر {method_name}.\n\n"
        "✍️ اكتب مبلغ الشحن، وبعدها بنرسل لك رابط الدفع:",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ الغاء", callback_data="cancel_topup")]]
        ),
    )
    return TOPUP_AMOUNT


async def receive_topup_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_required_channel_subscription(update, context):
        return ConversationHandler.END

    user = update.effective_user
    if not user:
        await update.message.reply_text("⚠️ تعذر معرفة المستخدم. حاول مرة اخرى.")
        return ConversationHandler.END

    remaining = get_active_payment_remaining_time(user.id)
    if remaining is not None and not is_admin(update) and not is_employee(update):
        time_str = format_remaining_time_arabic(remaining)
        await update.message.reply_text(
            "⚠️ لديك عملية دفع معلقة بالفعل.\n\n"
            "يرجى الانتظار حتى تنتهي صلاحيتها أو تكتمل قبل محاولة الشحن مرة أخرى.\n"
            f"الانتظار المتبقي: <b>{time_str}</b>.",
            parse_mode="HTML",
            reply_markup=wallet_keyboard(),
        )
        return ConversationHandler.END

    amount = parse_amount(update.message.text.strip(), default=-1)
    if amount <= 0:
        await update.message.reply_text("المبلغ لازم يكون رقم اكبر من 0. اكتب المبلغ مرة ثانية:")
        return TOPUP_AMOUNT

    topup_method = context.user_data.pop("topup_method", None)
    if topup_method not in {"nowpayments", "tap"}:
        await update.message.reply_text("انتهت جلسة الشحن. ابدأ من المحفظة مرة ثانية.", reply_markup=wallet_keyboard())
        return ConversationHandler.END

    if topup_method == "tap":
        try:
            charge = create_tap_charge(user, amount)
        except Exception as error:
            LOGGER.exception("Failed to create Tap Payments charge")
            await update.message.reply_text(
                "تعذر إنشاء طلب الدفع عبر Tap Payments حاليا.\n\n"
                f"السبب: {error}",
                reply_markup=wallet_keyboard(),
            )
            return ConversationHandler.END

        tap_charge_id = str(charge.get("id") or make_short_id())
        payment_url = get_tap_payment_url(charge)
        if not payment_url:
            LOGGER.error("Tap Payments charge response does not include a payment URL: %s", charge)
            await update.message.reply_text(
                "⚠️ تم إنشاء طلب Tap لكن لم يصل رابط الدفع. حاول مرة ثانية لاحقا.",
                reply_markup=wallet_keyboard(),
            )
            return ConversationHandler.END

        created_at = int(time.time())
        topup = {
            "id": make_short_id(),
            "user_id": user.id,
            "amount": amount,
            "credit_amount": amount * get_topup_credit_rate(),
            "price_currency": get_tap_currency(),
            "method": "tap_charge",
            "tap_charge_id": tap_charge_id,
            "order_id": charge.get("reference_id"),
            "invoice_url": payment_url,
            "payment_status": get_payment_status(charge) or "initiated",
            "credited": False,
            "created_at": created_at,
            "expires_at": created_at + TOPUP_LINK_TTL_SECONDS,
            "raw_invoice": charge,
        }
        add_topup(topup)

        sent_message = await update.message.reply_text(
            "✅ تم إنشاء رابط الدفع عبر Tap Payments.\n\n"
            f"رقم العملية: {tap_charge_id}\n"
            f"المبلغ: {format_price(amount)} {get_tap_currency()}\n\n"
            "الرابط صالح لمدة 20 دقيقة فقط. بعد اكتمال الدفع، البوت سيتحقق تلقائيا ويضيف الرصيد.",
            reply_markup=topup_invoice_keyboard(payment_url, "💸 فتح رابط الدفع"),
        )
        update_topup_by_id(
            str(topup["id"]),
            {
                "payment_message_chat_id": sent_message.chat_id,
                "payment_message_id": sent_message.message_id,
            },
        )
        return ConversationHandler.END

    else:
        # NOWPayments
        try:
            invoice = create_nowpayments_invoice(user.id, amount)
        except Exception as error:
            LOGGER.exception("Failed to create NOWPayments invoice")
            await update.message.reply_text(
                "تعذر إنشاء طلب الدفع حاليا.\n\n"
                f"السبب: {error}",
                reply_markup=wallet_keyboard(),
            )
            return ConversationHandler.END

        invoice_id = str(invoice.get("id") or invoice.get("invoice_id") or make_short_id())
        invoice_url = invoice.get("invoice_url") or invoice.get("url")
        if not invoice_url:
            LOGGER.error("NOWPayments invoice response does not include an invoice URL: %s", invoice)
            await update.message.reply_text(
                "⚠️ تم إنشاء الفاتورة لكن لم يصل رابط الدفع من NOWPayments. حاول مرة ثانية لاحقا.",
                reply_markup=wallet_keyboard(),
            )
            return ConversationHandler.END

        created_at = int(time.time())
        topup = {
            "id": make_short_id(),
            "user_id": user.id,
            "amount": amount,
            "credit_amount": amount * get_topup_credit_rate(),
            "price_currency": get_nowpayments_price_currency(),
            "method": "nowpayments_invoice",
            "invoice_id": invoice_id,
            "order_id": invoice.get("order_id"),
            "invoice_url": invoice_url,
            "payment_status": invoice.get("payment_status", "waiting"),
            "credited": False,
            "created_at": created_at,
            "expires_at": created_at + TOPUP_LINK_TTL_SECONDS,
            "raw_invoice": invoice,
        }
        payment_id = invoice.get("payment_id") or invoice.get("paymentId")
        if payment_id:
            topup["payment_id"] = str(payment_id)
        add_topup(topup)

        sent_message = await update.message.reply_text(
            "✅ تم إنشاء رابط الدفع عبر NOWPayments.\n\n"
            f"رقم الفاتورة: {invoice_id}\n"
            f"المبلغ: {format_price(amount)} {get_nowpayments_price_currency().upper()}\n\n"
            "افتح الرابط واختر العملة المناسبة من صفحة NOWPayments.\n"
            "بعد اكتمال الدفع، البوت سيتحقق تلقائيا خلال ثواني ويضيف الرصيد.",
            reply_markup=topup_invoice_keyboard(invoice_url, "💸 فتح رابط الدفع"),
        )
        update_topup_by_id(
            str(topup["id"]),
            {
                "payment_message_chat_id": sent_message.chat_id,
                "payment_message_id": sent_message.message_id,
            },
        )
        return ConversationHandler.END


async def cancel_topup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("topup_method", None)
    context.user_data.pop("verify_topup_id", None)

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await edit_message(query, "✅ تم الغاء طلب الشحن.", reply_markup=wallet_keyboard())
    else:
        await update.message.reply_text("✅ تم الغاء طلب الشحن.", reply_markup=wallet_keyboard())

    return ConversationHandler.END


async def start_topup_payment_verification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    topup_id = query.data.split(":", 1)[1]
    topup = get_topup_by_id(topup_id)
    if not topup or topup.get("user_id") != query.from_user.id:
        await edit_message(query, "طلب الشحن غير موجود.", reply_markup=wallet_keyboard())
        return ConversationHandler.END

    if topup.get("credited"):
        await edit_message(query, "هذا الطلب تم شحنه مسبقا.", reply_markup=wallet_keyboard())
        return ConversationHandler.END

    context.user_data["verify_topup_id"] = topup_id
    await edit_message(
        query,
        "📨 ارسل Payment ID الذي ظهر لك في صفحة NOWPayments بعد نجاح الدفع.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ الغاء", callback_data="cancel_topup")]]
        ),
    )
    return TOPUP_PAYMENT_ID


async def start_latest_topup_payment_verification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    topup = get_latest_uncredited_topup(query.from_user.id)
    if not topup:
        await edit_message(query, "ما عندك طلب شحن بانتظار التحقق.", reply_markup=wallet_keyboard())
        return ConversationHandler.END

    context.user_data["verify_topup_id"] = topup["id"]
    await edit_message(
        query,
        "📨 ارسل Payment ID الذي ظهر لك في صفحة NOWPayments بعد نجاح الدفع.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ الغاء", callback_data="cancel_topup")]]
        ),
    )
    return TOPUP_PAYMENT_ID


async def receive_topup_payment_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not user:
        await update.message.reply_text("⚠️ تعذر معرفة المستخدم. حاول مرة اخرى.")
        return ConversationHandler.END

    topup_id = context.user_data.pop("verify_topup_id", None)
    topup = get_topup_by_id(topup_id) if topup_id else None
    if not topup or topup.get("user_id") != user.id:
        await update.message.reply_text("انتهت جلسة التحقق. افتح المحفظة وحاول مرة ثانية.", reply_markup=wallet_keyboard())
        return ConversationHandler.END

    if topup.get("credited"):
        await update.message.reply_text("هذا الطلب تم شحنه مسبقا.", reply_markup=wallet_keyboard())
        return ConversationHandler.END

    payment_id = update.message.text.strip()
    if not payment_id:
        await update.message.reply_text("📨 ارسل Payment ID بشكل صحيح:")
        return TOPUP_PAYMENT_ID

    try:
        payment = get_nowpayments_payment(payment_id)
    except Exception as error:
        LOGGER.exception("Failed to verify NOWPayments invoice payment")
        await update.message.reply_text(
            "تعذر التحقق من الدفع حاليا.\n\n"
            f"السبب: {error}",
            reply_markup=wallet_keyboard(),
        )
        return ConversationHandler.END

    status = payment.get("payment_status", "unknown")
    updates = {
        "payment_id": payment_id,
        "payment_status": status,
        "raw_status": payment,
    }

    if not payment_matches_topup(payment, topup):
        update_topup_by_id(topup_id, updates)
        await update.message.reply_text(
            "Payment ID لا يطابق فاتورة الشحن هذه.\n"
            "تأكد من الرقم الموجود في صفحة الدفع الخاصة بنفس الطلب.",
            reply_markup=wallet_keyboard(),
        )
        return ConversationHandler.END

    success_statuses = {"finished", "confirmed", "sending"}
    if status in success_statuses:
        credit_amount = parse_amount(topup.get("credit_amount", topup.get("amount", 0)))
        change_user_wallet(user.id, credit_amount)
        updates["credited"] = True
        updates["credited_at"] = int(time.time())
        update_topup_by_id(topup_id, updates)
        await update.message.reply_text(
            "✅ تم تأكيد الدفع وإضافة الرصيد بنجاح.\n\n"
            f"المبلغ المضاف: {format_price(credit_amount)}",
            reply_markup=wallet_keyboard(),
        )
        return ConversationHandler.END

    update_topup_by_id(topup_id, updates)
    await update.message.reply_text(
        "الدفع لم يكتمل حسب NOWPayments حتى الآن.\n\n"
        f"الحالة الحالية: {status}",
        reply_markup=wallet_keyboard(),
    )
    return ConversationHandler.END


async def start_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if not is_admin(update):
        await edit_message(query, "🔒 هذه العملية مخصصة للادمن فقط.")
        return ConversationHandler.END

    context.user_data["new_product"] = {}
    await edit_message(
        query,
        "اضافة منتج جديد.\n\n"
        "✍️ اكتب اسم المنتج:",
        reply_markup=product_flow_keyboard(),
    )
    return PRODUCT_NAME


async def receive_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update):
        await update.message.reply_text("🔒 هذه العملية مخصصة للادمن فقط.")
        return ConversationHandler.END

    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("اسم المنتج لا يمكن يكون فاضي. اكتب اسم المنتج:")
        return PRODUCT_NAME

    context.user_data.setdefault("new_product", {})["name"] = name
    await update.message.reply_text(
        "✍️ اكتب وصف المنتج.\n\n"
        "اذا ما تبي تضيف وصف، ارسل -",
        reply_markup=product_flow_keyboard(),
    )
    return PRODUCT_DESCRIPTION


async def receive_product_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update):
        await update.message.reply_text("🔒 هذه العملية مخصصة للادمن فقط.")
        return ConversationHandler.END

    description = update.message.text.strip()
    context.user_data.setdefault("new_product", {})["description"] = (
        "" if description == "-" else description
    )
    await update.message.reply_text(
        "✍️ اكتب سعر المنتج بالريال:",
        reply_markup=product_flow_keyboard(),
    )
    return PRODUCT_PRICE


async def receive_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update):
        await update.message.reply_text("🔒 هذه العملية مخصصة للادمن فقط.")
        return ConversationHandler.END

    raw_price = update.message.text.strip()
    try:
        price = float(raw_price)
    except ValueError:
        await update.message.reply_text("السعر لازم يكون رقم. مثال: 25 او 19.99")
        return PRODUCT_PRICE

    if price < 0:
        await update.message.reply_text("السعر لازم يكون 0 أو أكثر. اكتب السعر مرة ثانية:")
        return PRODUCT_PRICE

    product = context.user_data.pop("new_product", {})
    product["id"] = uuid4().hex
    product["price"] = int(price) if price.is_integer() else price

    products = load_products()
    products.append(product)
    save_products(products)

    description = product.get("description") or "لا يوجد وصف"
    await update.message.reply_text(
        "تمت اضافة المنتج بنجاح.\n\n"
        f"اسم المنتج: {product['name']}\n"
        f"الوصف: {description}\n"
        f"السعر: {product['price']} ريال",
        reply_markup=admin_keyboard(),
    )
    return ConversationHandler.END


async def cancel_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("new_product", None)

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await edit_message(
            query,
            "✅ تم الغاء اضافة المنتج.",
            reply_markup=admin_keyboard(),
        )
    else:
        await update.message.reply_text(
            "✅ تم الغاء اضافة المنتج.",
            reply_markup=admin_keyboard(),
        )

    return ConversationHandler.END


async def start_add_username_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if not is_admin(update):
        await edit_message(query, "🔒 هذه العملية مخصصة للادمن فقط.")
        return ConversationHandler.END

    await edit_message(
        query,
        "اضافة قسم يوزرات جديد.\n\n"
        "✍️ اكتب اسم القسم:",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ الغاء", callback_data="cancel_username_admin_flow")]]
        ),
    )
    return USERNAME_CATEGORY_NAME


async def receive_username_category_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update):
        await update.message.reply_text("🔒 هذه العملية مخصصة للادمن فقط.")
        return ConversationHandler.END

    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("اسم القسم لا يمكن يكون فاضي. اكتب اسم القسم:")
        return USERNAME_CATEGORY_NAME

    store = load_username_store()
    store.setdefault("categories", []).append({"id": make_short_id(), "name": name, "items": []})
    save_username_store(store)

    await update.message.reply_text(
        "تمت اضافة قسم اليوزرات بنجاح.",
        reply_markup=admin_usernames_keyboard(),
    )
    return ConversationHandler.END


async def start_add_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if not can_manage_usernames(update):
        await edit_message(query, "🚫 هذه العملية غير متاحة لك.")
        return ConversationHandler.END

    category_id = query.data.split(":", 1)[1]
    category = get_username_category(category_id)
    if not category:
        await edit_message(
            query,
            "القسم غير موجود.",
            reply_markup=back_to_admin_username_categories_keyboard(),
        )
        return ConversationHandler.END

    context.user_data["new_username"] = {"category_id": category_id}
    await edit_message(
        query,
        "اضافة يوزر جديد.\n\n"
        f"القسم: {category.get('name', 'قسم بدون اسم')}\n\n"
        "✍️ اكتب اسم اليوزر:",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ الغاء", callback_data="cancel_username_admin_flow")]]
        ),
    )
    return USERNAME_NAME


async def receive_username_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not can_manage_usernames(update):
        await update.message.reply_text("🚫 هذه العملية غير متاحة لك.")
        return ConversationHandler.END

    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("اسم اليوزر لا يمكن يكون فاضي. اكتب اسم اليوزر:")
        return USERNAME_NAME

    context.user_data.setdefault("new_username", {})["name"] = name
    await update.message.reply_text("✍️ اكتب سعر اليوزر بالريال:")
    return USERNAME_PRICE


async def receive_username_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not can_manage_usernames(update):
        await update.message.reply_text("🚫 هذه العملية غير متاحة لك.")
        return ConversationHandler.END

    raw_price = update.message.text.strip()
    try:
        price = float(raw_price)
    except ValueError:
        await update.message.reply_text("السعر لازم يكون رقم. مثال: 250 او 199.99")
        return USERNAME_PRICE

    if price < 0:
        await update.message.reply_text("السعر لازم يكون 0 أو أكثر. اكتب السعر مرة ثانية:")
        return USERNAME_PRICE

    context.user_data.setdefault("new_username", {})["price"] = int(price) if price.is_integer() else price
    await update.message.reply_text(
        "📨 ارسل معلومات اليوزر.\n\n"
    )
    return USERNAME_DELIVERY


def build_delivery_from_message(message) -> dict | None:
    if message.text:
        return {"type": "text", "text": message.text}
    if message.document:
        return {
            "type": "document",
            "file_id": message.document.file_id,
            "file_name": message.document.file_name,
        }
    if message.video:
        return {
            "type": "video",
            "file_id": message.video.file_id,
            "file_name": message.video.file_name,
        }
    return None


async def receive_username_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not can_manage_usernames(update):
        await update.message.reply_text("🚫 هذه العملية غير متاحة لك.")
        return ConversationHandler.END

    delivery = build_delivery_from_message(update.message)
    if not delivery:
        await update.message.reply_text("📨 ارسل نص، ملف، او مقطع فيديو فقط.")
        return USERNAME_DELIVERY

    new_username = context.user_data.pop("new_username", {})
    category_id = new_username.get("category_id")
    category = get_username_category(category_id) if category_id else None
    if not category:
        await update.message.reply_text(
            "القسم غير موجود.",
            reply_markup=back_to_admin_username_categories_keyboard(),
        )
        return ConversationHandler.END

    item = {
        "id": make_short_id(),
        "name": new_username.get("name", "يوزر بدون اسم"),
        "price": new_username.get("price", 0),
        "delivery": delivery,
        "status": "available",
        "added_by": get_actor_info(
            update.effective_user,
            "admin" if is_admin(update) else "employee",
        ),
        "added_at": int(time.time()),
    }
    category.setdefault("items", []).append(item)
    update_username_category(category_id, category)
    log_staff_operation(
        update.effective_user,
        "admin" if is_admin(update) else "employee",
        "add_username",
        {
            "category_id": category_id,
            "category_name": category.get("name", "قسم بدون اسم"),
            "username_id": item["id"],
            "username_name": item["name"],
            "price": item["price"],
        },
    )

    await update.message.reply_text(
        "تمت اضافة اليوزر بنجاح.\n\n"
        f"اليوزر: {item['name']}\n"
        f"السعر: {format_price(get_username_price(item))} ريال",
        reply_markup=(
            admin_username_category_keyboard(category_id)
            if is_admin(update)
            else employee_username_category_keyboard(category_id)
        ),
    )
    return ConversationHandler.END


async def cancel_username_admin_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("new_username", None)

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await edit_message(
            query,
            "✅ تم الالغاء.",
            reply_markup=admin_usernames_keyboard() if is_admin(update) else employee_keyboard(),
        )
    else:
        await update.message.reply_text(
            "✅ تم الالغاء.",
            reply_markup=admin_usernames_keyboard() if is_admin(update) else employee_keyboard(),
        )

    return ConversationHandler.END


async def start_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if not can_manage_stock(update):
        await edit_message(query, "🚫 هذه العملية غير متاحة لك.")
        return ConversationHandler.END

    product_id = query.data.split(":", 1)[1]
    product = get_product(product_id)
    if not product:
        await edit_message(
            query,
            "المنتج غير موجود.",
            reply_markup=back_to_admin_products_keyboard(),
        )
        return ConversationHandler.END

    context.user_data["delivery_product_id"] = product_id
    await edit_message(
        query,
        "التسليم التلقائي.\n\n"
        f"المنتج: {product.get('name', 'منتج بدون اسم')}\n\n"
        "📨 ارسل نص التسليم التلقائي، او ارسل ملف، او مقطع فيديو.\n"
        "كل رسالة تضيف كمية واحدة للمخزون.",
        reply_markup=delivery_flow_keyboard(),
    )
    return DELIVERY_CONTENT


async def receive_delivery_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not can_manage_stock(update):
        await update.message.reply_text("🚫 هذه العملية غير متاحة لك.")
        return ConversationHandler.END

    product_id = context.user_data.get("delivery_product_id")
    product = get_product(product_id) if product_id else None
    if not product:
        await update.message.reply_text(
            "المنتج غير موجود.",
            reply_markup=back_to_admin_products_keyboard(),
        )
        return ConversationHandler.END

    message = update.message
    if message.text:
        delivery = {
            "type": "text",
            "text": message.text,
        }
    elif message.document:
        delivery = {
            "type": "document",
            "file_id": message.document.file_id,
            "file_name": message.document.file_name,
        }
    elif message.video:
        delivery = {
            "type": "video",
            "file_id": message.video.file_id,
            "file_name": message.video.file_name,
        }
    else:
        await message.reply_text("📨 ارسل نص، ملف، او مقطع فيديو فقط.")
        context.user_data["delivery_product_id"] = product_id
        return DELIVERY_CONTENT

    delivery_items = get_delivery_items(product)
    delivery_items.append(delivery)
    product["delivery_items"] = delivery_items
    product.pop("delivery", None)
    update_product(product_id, product)
    log_staff_operation(
        update.effective_user,
        "admin" if is_admin(update) else "employee",
        "add_product_stock",
        {
            "product_id": product_id,
            "product_name": product.get("name", "منتج بدون اسم"),
            "stock_count_after": len(delivery_items),
            "delivery_type": delivery.get("type"),
            "price": product.get("price", 0),
        },
    )

    await message.reply_text(
        "✅ تم اضافة عنصر تسليم تلقائي للمخزون بنجاح.\n\n"
        f"الكمية المتوفرة الان: {len(delivery_items)}\n\n"
        "📨 ارسل العنصر التالي، او اضغط التوقف عن اضافه التسليم.",
        reply_markup=delivery_flow_keyboard(),
    )
    return DELIVERY_CONTENT


async def stop_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    product_id = context.user_data.pop("delivery_product_id", None)
    product = get_product(product_id) if product_id else None
    if is_admin(update):
        reply_markup = product_admin_keyboard(product_id) if product_id else admin_keyboard()
    else:
        reply_markup = employee_keyboard()
    quantity = len(get_delivery_items(product)) if product else 0

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await edit_message(
            query,
            "✅ تم التوقف عن اضافه التسليم التلقائي.\n\n"
            f"الكمية المتوفرة: {quantity}",
            reply_markup=reply_markup,
        )
    else:
        await update.message.reply_text(
            "✅ تم التوقف عن اضافه التسليم التلقائي.\n\n"
            f"الكمية المتوفرة: {quantity}",
            reply_markup=reply_markup,
        )

    return ConversationHandler.END


async def send_delivery_item(update: Update, delivery_item: dict) -> None:
    message = update.callback_query.message
    await send_delivery_item_to_chat(message, delivery_item)


async def send_delivery_item_to_chat(target, delivery_item: dict) -> None:
    delivery_type = delivery_item.get("type")

    if delivery_type == "text":
        await target.reply_text(
            f"""
✅ تمت عملية الشراء بنجاح!
----------

{delivery_item.get('text', '')}

----------
نتمنى لك تجربة رائعة 😍🤍
            """
        )
        return

    if delivery_type == "document":
        await target.reply_document(
            document=delivery_item.get("file_id"),
            caption="تسليم المنتج",
        )
        return

    if delivery_type == "video":
        await target.reply_video(
            video=delivery_item.get("file_id"),
            caption="تسليم المنتج",
        )
        return

    await target.reply_text("✅ تم الشراء، لكن نوع التسليم غير معروف. تواصل مع الدعم.")


async def send_delivery_item_by_bot(bot, chat_id: int, delivery_item: dict) -> None:
    delivery_type = delivery_item.get("type")
    if delivery_type == "text":
        await bot.send_message(
            chat_id=chat_id,
            text=(
                "✅ تمت عملية الشراء بنجاح!\n"
                "----------\n\n"
                f"{delivery_item.get('text', '')}\n\n"
                "----------\n"
                "نتمنى لك تجربة رائعة, لا تنسى تقيمنا هنا @l2rb5 😍🤍"
            ),
        )
        return
    if delivery_type == "document":
        await bot.send_document(
            chat_id=chat_id,
            document=delivery_item.get("file_id"),
            caption="تسليم المنتج",
        )
        return
    if delivery_type == "video":
        await bot.send_video(
            chat_id=chat_id,
            video=delivery_item.get("file_id"),
            caption="تسليم المنتج",
        )
        return
    await bot.send_message(chat_id=chat_id, text="✅ تم الشراء، لكن نوع التسليم غير معروف. تواصل مع الدعم.")


def direct_payment_text(item_name: str, amount: float, payment_id: str) -> str:
    return (
        "💳 الدفع المباشر.\n\n"
        f"الطلب: {item_name}\n"
        f"المبلغ: {format_price(amount)} {get_tap_currency()}\n"
        f"رقم الدفع: {payment_id}\n\n"
        "الرابط صالح لمدة 20 دقيقة. بعد اكتمال الدفع يتم التسليم تلقائيا."
    )


async def create_direct_purchase_payment(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    amount: float,
    item_name: str,
    purchase: dict,
) -> None:
    query = update.callback_query
    user = update.effective_user
    if not user:
        await edit_message(query, "⚠️ تعذر معرفة المستخدم. حاول مرة اخرى.")
        return

    payment_id = str(purchase.get("payment_id") or make_short_id())
    purchase["payment_id"] = payment_id

    context.user_data[f"pending_direct_purchase_{payment_id}"] = {
        "amount": amount,
        "item_name": item_name,
        "purchase": purchase,
    }

    keyboard = [
        [
            InlineKeyboardButton("💸 البطاقة / Apple Pay", callback_data=f"direct_pay_method:tap:{payment_id}"),
            InlineKeyboardButton("💳 NOWPayments", callback_data=f"direct_pay_method:nowpayments:{payment_id}"),
        ],
        [InlineKeyboardButton("❌ الغاء", callback_data=f"direct_pay_cancel:{payment_id}")],
    ]

    await edit_message(
        query,
        f"🛒 طلب جديد: {item_name}\n"
        f"المبلغ: {format_price(amount)} ريال\n\n"
        "👇 اختر طريقة الدفع المناسبة لك:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def process_direct_payment_method(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    method: str,
    payment_id: str,
) -> None:
    query = update.callback_query
    user = update.effective_user
    if not user:
        await edit_message(query, "⚠️ تعذر معرفة المستخدم. حاول مرة اخرى.")
        return

    pending_key = f"pending_direct_purchase_{payment_id}"
    pending = context.user_data.pop(pending_key, None)
    if not pending:
        await edit_message(query, "⚠️ انتهت صلاحية هذا الطلب أو تم إلغاؤه. الرجاء المحاولة مرة أخرى.", reply_markup=back_keyboard())
        return

    amount = pending["amount"]
    item_name = pending["item_name"]
    purchase = pending["purchase"]

    if method == "tap":
        try:
            charge = create_tap_charge(
                user,
                amount,
                description=f"Direct purchase: {item_name}",
                reference_prefix="TAP-ORDER",
                metadata={
                    "payment_id": payment_id,
                    "purchase_type": str(purchase.get("type", "")),
                },
            )
        except Exception as error:
            LOGGER.exception("Failed to create direct Tap payment")
            release_direct_purchase_hold({"id": payment_id, "purchase": purchase})
            await edit_message(
                query,
                "تعذر إنشاء رابط الدفع حاليا.\n\n"
                f"السبب: {error}",
                reply_markup=back_keyboard(),
            )
            return

        payment_url = get_tap_payment_url(charge)
        if not payment_url:
            release_direct_purchase_hold({"id": payment_id, "purchase": purchase})
            await edit_message(query, "⚠️ تم إنشاء طلب الدفع لكن لم يصل الرابط. حاول مرة ثانية لاحقا.", reply_markup=back_keyboard())
            return

        created_at = int(time.time())
        payment = {
            "id": payment_id,
            "user_id": user.id,
            "user_name": get_user_display_name(user),
            "username": user.username or "",
            "amount": amount,
            "price_currency": get_tap_currency(),
            "method": "tap_charge",
            "kind": "direct_purchase",
            "tap_charge_id": str(charge.get("id") or ""),
            "order_id": charge.get("reference_id"),
            "invoice_url": payment_url,
            "payment_status": get_payment_status(charge) or "initiated",
            "credited": False,
            "created_at": created_at,
            "expires_at": created_at + TOPUP_LINK_TTL_SECONDS,
            "purchase": purchase,
            "raw_invoice": charge,
        }
        add_topup(payment)

        await edit_message(
            query,
            direct_payment_text(item_name, amount, payment_id),
            reply_markup=direct_payment_keyboard(payment_url),
        )
        if query.message:
            update_topup_by_id(
                payment_id,
                {
                    "payment_message_chat_id": query.message.chat_id,
                    "payment_message_id": query.message.message_id,
                },
            )

    elif method == "nowpayments":
        divided_amount = amount / 4.0
        try:
            invoice = create_nowpayments_invoice(user.id, divided_amount)
        except Exception as error:
            LOGGER.exception("Failed to create direct NOWPayments invoice")
            release_direct_purchase_hold({"id": payment_id, "purchase": purchase})
            await edit_message(
                query,
                "تعذر إنشاء رابط الدفع حاليا.\n\n"
                f"السبب: {error}",
                reply_markup=back_keyboard(),
            )
            return

        invoice_id = str(invoice.get("id") or invoice.get("invoice_id") or make_short_id())
        invoice_url = invoice.get("invoice_url") or invoice.get("url")
        if not invoice_url:
            release_direct_purchase_hold({"id": payment_id, "purchase": purchase})
            LOGGER.error("NOWPayments invoice response does not include an invoice URL: %s", invoice)
            await edit_message(
                query,
                "⚠️ تم إنشاء الفاتورة لكن لم يصل رابط الدفع من NOWPayments. حاول مرة ثانية لاحقا.",
                reply_markup=back_keyboard(),
            )
            return

        created_at = int(time.time())
        payment = {
            "id": payment_id,
            "user_id": user.id,
            "user_name": get_user_display_name(user),
            "username": user.username or "",
            "amount": divided_amount,
            "price_currency": get_nowpayments_price_currency(),
            "method": "nowpayments_invoice",
            "kind": "direct_purchase",
            "invoice_id": invoice_id,
            "order_id": invoice.get("order_id"),
            "invoice_url": invoice_url,
            "payment_status": invoice.get("payment_status", "waiting"),
            "credited": False,
            "created_at": created_at,
            "expires_at": created_at + TOPUP_LINK_TTL_SECONDS,
            "purchase": purchase,
            "raw_invoice": invoice,
        }
        payment_invoice_id = invoice.get("payment_id") or invoice.get("paymentId")
        if payment_invoice_id:
            payment["payment_id"] = str(payment_invoice_id)
        add_topup(payment)

        await edit_message(
            query,
            f"✅ تم إنشاء رابط الدفع عبر NOWPayments.\n\n"
            f"الطلب: {item_name}\n"
            f"المبلغ: {format_price(divided_amount)} {get_nowpayments_price_currency().upper()}\n"
            f"رقم الفاتورة: {invoice_id}\n\n"
            "الرابط صالح لمدة 20 دقيقة. بعد اكتمال الدفع، البوت سيتحقق تلقائيا ويقوم بتسليم الطلب.",
            reply_markup=direct_payment_keyboard(invoice_url),
        )
        if query.message:
            update_topup_by_id(
                payment_id,
                {
                    "payment_message_chat_id": query.message.chat_id,
                    "payment_message_id": query.message.message_id,
                },
            )


async def process_direct_payment_cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    payment_id: str,
) -> None:
    query = update.callback_query
    user = update.effective_user
    if not user:
        await edit_message(query, "⚠️ تعذر معرفة المستخدم. حاول مرة اخرى.")
        return

    pending_key = f"pending_direct_purchase_{payment_id}"
    pending = context.user_data.pop(pending_key, None)
    if pending:
        purchase = pending["purchase"]
        release_direct_purchase_hold({"id": payment_id, "purchase": purchase})
    else:
        topup = get_topup_by_id(payment_id) or get_topup(payment_id)
        if topup:
            release_direct_purchase_hold(topup)

    await edit_message(query, "✅ تم إلغاء طلب الشراء.", reply_markup=back_keyboard())


def release_direct_purchase_hold(payment: dict) -> None:
    purchase = payment.get("purchase", {})
    if not isinstance(purchase, dict) or payment.get("hold_released") or payment.get("credited"):
        return

    purchase_type = purchase.get("type")
    if purchase_type == "digital_product":
        product_id = purchase.get("product_id")
        delivery_item = purchase.get("delivery")
        product = get_product(product_id) if product_id else None
        if product and isinstance(delivery_item, dict):
            delivery_items = get_delivery_items(product)
            delivery_items.insert(0, delivery_item)
            product["delivery_items"] = delivery_items
            product.pop("delivery", None)
            update_product(product_id, product)
    elif purchase_type == "username":
        category_id = purchase.get("category_id")
        item_id = purchase.get("item_id")
        item = get_username_item(category_id, item_id) if category_id and item_id else None
        pending = item.get("pending_payment", {}) if item else {}
        if item and item.get("status") == "pending_payment" and pending.get("payment_id") == purchase.get("payment_id"):
            item["status"] = "available"
            item.pop("pending_payment", None)
            update_username_item(category_id, item_id, item)

    payment_id = str(payment.get("id") or purchase.get("payment_id") or "")
    if payment_id:
        update_topup_by_id(payment_id, {"hold_released": True, "hold_released_at": int(time.time())})


def direct_payment_customer(payment: dict) -> str:
    username = f"@{payment.get('username')}" if payment.get("username") else "لا يوجد"
    return f"{payment.get('user_name', 'غير معروف')} | {username} | {payment.get('user_id')}"


async def notify_staff_about_direct_order(bot, payment: dict, order: dict) -> None:
    item_type_label = {
        "digital_product": "منتج رقمي",
        "username": "يوزر",
    }.get(order.get("item_type"), order.get("item_type", "غير معروف"))
    amount = format_price(parse_amount(order.get("amount", 0)))
    text = (
        "🛒 طلب جديد وصل.\n\n"
        f"🔖 رقم الطلب: {order.get('order_number', 'غير متوفر')}\n"
        f"📦 النوع: {item_type_label}\n"
        f"📝 المنتج: {order.get('item_name', 'عنصر بدون اسم')}\n"
        f"💰 المبلغ: {amount} ريال\n"
        f"👤 العميل: {direct_payment_customer(payment)}"
    )
    for staff_id in get_staff_ids():
        try:
            await bot.send_message(chat_id=staff_id, text=text)
        except Exception:
            LOGGER.exception("Failed to notify staff %s about direct order", staff_id)


async def fulfill_direct_purchase_payment(bot, payment: dict, raw_payment: dict) -> None:
    purchase = payment.get("purchase", {})
    if not isinstance(purchase, dict) or payment.get("credited"):
        return

    user_id = int(payment["user_id"])
    purchase_type = purchase.get("type")
    if purchase_type == "digital_product":
        delivery_item = purchase.get("delivery", {})
        order = add_purchase_operation(
            user_id=user_id,
            item_type="digital_product",
            item_name=purchase.get("item_name", "منتج بدون اسم"),
            amount=parse_amount(payment.get("amount", 0)),
            source="direct_payment",
            details={"product_id": purchase.get("product_id"), "delivery": delivery_item},
        )
    elif purchase_type == "username":
        category_id = purchase.get("category_id")
        item_id = purchase.get("item_id")
        item = get_username_item(category_id, item_id) if category_id and item_id else None
        if item:
            item["status"] = "sold"
            item["sold_to"] = user_id
            item["sold_at"] = int(time.time())
            item.pop("pending_payment", None)
        delivery_item = (item or purchase).get("delivery", {})
        order = add_purchase_operation(
            user_id=user_id,
            item_type="username",
            item_name=purchase.get("item_name", "يوزر بدون اسم"),
            amount=parse_amount(payment.get("amount", 0)),
            source="direct_payment",
            details={"category_id": category_id, "item_id": item_id, "delivery": delivery_item},
        )
        if item:
            archive_sold_username(category_id, item_id, item, order["order_number"], user_id)
    else:
        LOGGER.warning("Unknown direct purchase type for payment %s: %s", payment.get("id"), purchase_type)
        return

    updates = {
        "payment_status": get_payment_status(raw_payment) or "captured",
        "credited": True,
        "credited_at": int(time.time()),
        "fulfilled": True,
        "fulfilled_at": int(time.time()),
        "order_number": order["order_number"],
        "raw_status": raw_payment,
    }
    if raw_payment.get("payment_id"):
        updates["payment_id"] = raw_payment.get("payment_id")
    update_topup_by_id(str(payment["id"]), updates)

    await notify_staff_about_direct_order(bot, payment, order)
    try:
        chat_id = int(payment.get("payment_message_chat_id") or user_id)
        message_id = payment.get("payment_message_id")
        if message_id:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=int(message_id),
                text=(
                    "✅ تم تأكيد الدفع بنجاح.\n\n"
                    f"رقم الطلب: {order['order_number']}\n"
                    f"المنتج: {order.get('item_name', 'عنصر بدون اسم')}\n"
                    f"المبلغ المدفوع: {format_price(parse_amount(order.get('amount', 0)))} ريال"
                ),
                reply_markup=back_keyboard(),
            )
    except BadRequest:
        pass
    except Exception:
        LOGGER.exception("Failed to update direct payment message %s", payment.get("id"))

    await send_delivery_item_by_bot(bot, user_id, order.get("details", {}).get("delivery", {}))


async def buy_product(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: str) -> None:
    query = update.callback_query
    user = update.effective_user

    if not user:
        await edit_message(query, "⚠️ تعذر معرفة المستخدم. حاول مرة اخرى.")
        return

    remaining = get_active_payment_remaining_time(user.id)
    if remaining is not None and not is_admin(update) and not is_employee(update):
        time_str = format_remaining_time_arabic(remaining)
        await edit_message(
            query,
            "⚠️ لديك عملية دفع معلقة بالفعل.\n\n"
            "يرجى الانتظار حتى تنتهي صلاحيتها أو تكتمل قبل محاولة الشراء مرة أخرى.\n"
            f"الانتظار المتبقي: <b>{time_str}</b>.",
            reply_markup=back_keyboard(),
            parse_mode="HTML",
        )
        return

    product = get_product(product_id)
    if not product:
        await edit_message(query, "المنتج غير موجود.", reply_markup=back_keyboard())
        return

    delivery_items = get_delivery_items(product)
    if not delivery_items:
        await edit_message(
            query,
            "المنتج غير متوفر حاليا.\n\n"
            "📭 لا توجد كمية متاحة للتسليم التلقائي.",
            reply_markup=product_purchase_keyboard(product_id),
        )
        return

    price = get_product_price(product)
    admin_purchase = is_admin(update)

    delivery_item = delivery_items.pop(0)
    product["delivery_items"] = delivery_items
    product.pop("delivery", None)
    update_product(product_id, product)

    if not admin_purchase:
        await create_direct_purchase_payment(
            update,
            context,
            price,
            product.get("name", "منتج بدون اسم"),
            {
                "type": "digital_product",
                "product_id": product_id,
                "item_name": product.get("name", "منتج بدون اسم"),
                "delivery": delivery_item,
            },
        )
        return

    paid_amount = 0 if admin_purchase else price
    order = add_purchase_operation(
        user_id=user.id,
        item_type="digital_product",
        item_name=product.get("name", "منتج بدون اسم"),
        amount=paid_amount,
        source="digital_products",
        details={"product_id": product_id, "delivery": delivery_item},
    )
    await notify_staff_about_order(context, user, order)
    await edit_message(
        query,
        "تمت عملية الشراء بنجاح.\n\n"
        f"رقم الطلب: {order['order_number']}\n"
        f"المنتج: {product.get('name', 'منتج بدون اسم')}\n"
        f"المبلغ المخصوم: {format_price(paid_amount)} ريال\n"
        f"الكمية المتبقية: {len(delivery_items)}",
        reply_markup=back_keyboard(),
    )
    await send_delivery_item(update, delivery_item)


def format_usernames_categories() -> tuple[str, InlineKeyboardMarkup]:
    release_expired_username_pending_payments()
    categories = get_username_categories()
    if not categories:
        return "🔤 قسم اليوزرات.\n\n📭 لا توجد اقسام متاحة حاليا.", back_keyboard()

    return (
        "🔤 قسم اليوزرات.\n\n👇 اختر القسم الذي تريده:",
        username_categories_keyboard(categories, "username_category"),
    )


def format_username_category(category: dict) -> tuple[str, InlineKeyboardMarkup]:
    release_expired_username_pending_payments()
    category = get_username_category(category.get("id")) or category
    available_items = [
        item for item in category.get("items", []) if item.get("status", "available") == "available"
    ]
    if not available_items:
        return (
            f"📁 قسم {category.get('name', 'بدون اسم')}.\n\n📭 لا توجد يوزرات متاحة حاليا.",
            back_to_username_categories_keyboard(),
        )

    return (
        f"📁 قسم {category.get('name', 'بدون اسم')}.\n\n👇 اختر اليوزر الذي تريده:",
        usernames_items_keyboard(category),
    )


def format_username_item(category: dict, item: dict) -> str:
    return (
        "تفاصيل اليوزر.\n\n"
        f"القسم: {category.get('name', 'بدون اسم')}\n"
        f"اسم اليوزر: {item.get('name', 'يوزر بدون اسم')}\n"
        f"السعر: {format_price(get_username_price(item))} ريال"
    )


def can_cancel_reservation(reservation: dict) -> bool:
    reserved_at = float(reservation.get("reserved_at", 0))
    return (time.time() - reserved_at) <= RESERVATION_CANCEL_SECONDS


async def buy_username_item(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    category_id: str,
    item_id: str,
) -> None:
    query = update.callback_query
    user = update.effective_user
    release_expired_username_pending_payments()
    item = get_username_item(category_id, item_id)

    if not user:
        await edit_message(query, "⚠️ تعذر معرفة المستخدم. حاول مرة اخرى.")
        return

    remaining = get_active_payment_remaining_time(user.id)
    if remaining is not None and not is_admin(update) and not is_employee(update):
        time_str = format_remaining_time_arabic(remaining)
        await edit_message(
            query,
            "⚠️ لديك عملية دفع معلقة بالفعل.\n\n"
            "يرجى الانتظار حتى تنتهي صلاحيتها أو تكتمل قبل محاولة الشراء مرة أخرى.\n"
            f"الانتظار المتبقي: <b>{time_str}</b>.",
            reply_markup=back_keyboard(),
            parse_mode="HTML",
        )
        return
    if not item:
        await edit_message(query, "اليوزر غير موجود.", reply_markup=back_keyboard())
        return
    if item.get("status", "available") != "available":
        await edit_message(query, "هذا اليوزر غير متاح حاليا.", reply_markup=back_keyboard())
        return

    price = get_username_price(item)
    admin_purchase = is_admin(update)

    if not admin_purchase:
        block_remaining = get_username_repurchase_block_remaining(user.id, category_id, item_id)
        if block_remaining:
            await edit_message(
                query,
                "لا يمكنك شراء نفس اليوزر مرة اخرى حاليا.\n\n"
                "بعد الضغط على شراء، يجب الانتظار يوم كامل قبل محاولة شراء نفس اليوزر مرة ثانية.\n"
                f"الوقت المتبقي: {format_duration_arabic(block_remaining)}",
                reply_markup=username_purchase_keyboard(category_id, item_id),
            )
            return

        if not is_employee(update):
            should_ban, recent_attempts = should_ban_for_username_purchase_attempt(user.id, category_id, item_id)
            if should_ban:
                now = int(time.time())
                current_attempt = {
                    "created_at": now,
                    "category_id": category_id,
                    "item_id": item_id,
                    "item_name": item.get("name", "يوزر بدون اسم"),
                    "payment_id": "blocked_before_payment",
                }
                all_attempts = recent_attempts + [current_attempt]
                reason = (
                    f"محاولة شراء {USERNAME_ABUSE_ATTEMPT_LIMIT} يوزرات مختلفة خلال "
                    f"{format_duration_arabic(USERNAME_ABUSE_WINDOW_SECONDS)}"
                )
                ban_user(
                    user.id,
                    reason,
                    {
                        "trigger": "rapid_username_purchase_attempts",
                        "window_seconds": USERNAME_ABUSE_WINDOW_SECONDS,
                        "attempt_limit": USERNAME_ABUSE_ATTEMPT_LIMIT,
                        "attempts": all_attempts,
                    },
                )
                await notify_admins_about_user_ban(context, user, reason, all_attempts)
                await edit_message(
                    query,
                    "🚫 تم حظر حسابك من استخدام البوت بسبب تكرار محاولات شراء اليوزرات خلال فترة قصيرة.",
                    reply_markup=None,
                )
                return

        payment_id = make_short_id()
        item["status"] = "pending_payment"
        item["pending_payment"] = {
            "payment_id": payment_id,
            "user_id": user.id,
            "created_at": int(time.time()),
            "expires_at": int(time.time()) + TOPUP_LINK_TTL_SECONDS,
        }
        update_username_item(category_id, item_id, item)
        await create_direct_purchase_payment(
            update,
            context,
            price,
            item.get("name", "يوزر بدون اسم"),
            {
                "type": "username",
                "payment_id": payment_id,
                "category_id": category_id,
                "item_id": item_id,
                "item_name": item.get("name", "يوزر بدون اسم"),
                "delivery": item.get("delivery", {}),
            },
        )
        return

    item["status"] = "sold"
    item["sold_to"] = user.id
    item["sold_at"] = int(time.time())
    order = add_purchase_operation(
        user_id=user.id,
        item_type="username",
        item_name=item.get("name", "يوزر بدون اسم"),
        amount=0 if admin_purchase else price,
        source="usernames",
        details={
            "category_id": category_id,
            "item_id": item_id,
            "delivery": item.get("delivery", {}),
        },
    )
    archive_sold_username(category_id, item_id, item, order["order_number"], user.id)
    await notify_staff_about_order(context, user, order)
    await edit_message(
        query,
        "✅ تم شراء اليوزر بنجاح.\n\n"
        f"رقم الطلب: {order['order_number']}\n"
        f"اليوزر: {item.get('name', 'يوزر بدون اسم')}\n"
        f"المبلغ المخصوم: {format_price(0 if admin_purchase else price)} ريال",
        reply_markup=back_keyboard(),
    )
    await send_delivery_item(update, item.get("delivery", {}))


async def reserve_username_item(update: Update, category_id: str, item_id: str) -> None:
    query = update.callback_query
    user = update.effective_user
    item = get_username_item(category_id, item_id)

    if not user:
        await edit_message(query, "⚠️ تعذر معرفة المستخدم. حاول مرة اخرى.")
        return

    remaining = get_active_payment_remaining_time(user.id)
    if remaining is not None and not is_admin(update) and not is_employee(update):
        time_str = format_remaining_time_arabic(remaining)
        await edit_message(
            query,
            "⚠️ لديك عملية دفع معلقة بالفعل.\n\n"
            "يرجى الانتظار حتى تنتهي صلاحيتها أو تكتمل قبل محاولة الحجز مرة أخرى.\n"
            f"الانتظار المتبقي: <b>{time_str}</b>.",
            reply_markup=back_keyboard(),
            parse_mode="HTML",
        )
        return
    if not item:
        await edit_message(query, "اليوزر غير موجود.", reply_markup=back_keyboard())
        return
    if item.get("status", "available") != "available":
        await edit_message(query, "هذا اليوزر غير متاح للحجز حاليا.", reply_markup=back_keyboard())
        return
    if user_has_active_reservation(user.id):
        await edit_message(
            query,
            "لديك حجز نشط بالفعل.\n\n"
            "يمكن لكل مستخدم امتلاك حجز واحد فقط. اكمل شراء الحجز الحالي او قم بالغائه اذا كان الالغاء متاحا.",
            reply_markup=back_keyboard(),
        )
        return
    block_remaining = get_username_re_reservation_block_remaining(user.id, category_id, item_id)
    if block_remaining:
        await edit_message(
            query,
            "لا يمكنك حجز نفس اليوزر مرة اخرى حاليا.\n\n"
            "بعد الغاء الحجز، يجب الانتظار يومين قبل حجز نفس اليوزر مرة ثانية.\n"
            f"الوقت المتبقي: {format_duration_arabic(block_remaining)}",
            reply_markup=username_purchase_keyboard(category_id, item_id),
        )
        return

    price = get_username_price(item)
    deposit = get_reservation_deposit(price)
    wallet = get_user_wallet(user.id)
    if wallet < deposit:
        await edit_message(
            query,
            "رصيدك غير كافي لحجز اليوزر.\n\n"
            f"قيمة الحجز: {format_price(deposit)} ريال\n"
            f"رصيدك الحالي: {format_price(wallet)} ريال",
            reply_markup=username_purchase_keyboard(category_id, item_id),
        )
        return

    now = int(time.time())
    set_user_wallet(user.id, wallet - deposit)
    item["status"] = "reserved"
    item["reservation"] = {
        "user_id": user.id,
        "username": user.username,
        "deposit": deposit,
        "reserved_at": now,
        "expires_at": now + RESERVATION_SECONDS,
    }
    update_username_item(category_id, item_id, item)
    add_user_operation(
        {
            "type": "reservation",
            "status": "active",
            "user_id": user.id,
            "item_type": "username",
            "item_name": item.get("name", "يوزر بدون اسم"),
            "amount": deposit,
            "expires_at": now + RESERVATION_SECONDS,
            "details": {
                "category_id": category_id,
                "item_id": item_id,
                "full_price": price,
                "remaining": price - deposit,
            },
        }
    )
    sync_bot_user_amounts(user.id)

    remaining = price - deposit
    await edit_message(
        query,
        "✅ تم حجز اليوزر بنجاح.\n\n"
        f"اليوزر: {item.get('name', 'يوزر بدون اسم')}\n"
        f"قيمة اليوزر: {format_price(price)} ريال\n"
        f"✅ تم خصم ثلث القيمة للحجز: {format_price(deposit)} ريال\n"
        f"المتبقي عند الشراء: {format_price(remaining)} ريال\n\n"
        "مدة الحجز 24 ساعة. يمكنك ادارة الحجز من زر العمليات. الغاء الحجز متاح خلال ساعة واحدة فقط، وبعدها يبقى المبلغ محجوزا حتى يحرره الادمن.",
        reply_markup=username_reserved_keyboard(category_id, item_id, can_cancel=True),
    )


async def cancel_username_reservation(update: Update, category_id: str, item_id: str) -> None:
    query = update.callback_query
    user = update.effective_user
    item = get_username_item(category_id, item_id)

    if not user or not item or item.get("status") != "reserved":
        await edit_message(query, "لا يوجد حجز نشط لهذا اليوزر.", reply_markup=back_keyboard())
        return

    reservation = item.get("reservation", {})
    if reservation.get("user_id") != user.id:
        await edit_message(query, "هذا الحجز ليس لك.", reply_markup=back_keyboard())
        return
    if not can_cancel_reservation(reservation):
        await edit_message(
            query,
            "انتهت مدة الغاء الحجز.\n\n"
            "الغاء الحجز متاح لمدة ساعة واحدة فقط. المبلغ سيبقى محجوزا حتى يحرره الادمن.",
            reply_markup=username_reserved_keyboard(category_id, item_id, can_cancel=False),
        )
        return

    deposit = float(reservation.get("deposit", 0))
    change_user_wallet(user.id, deposit)
    item["status"] = "available"
    item.pop("reservation", None)
    update_username_item(category_id, item_id, item)
    reservation_operation = find_user_operation_by_reservation(category_id, item_id)
    if reservation_operation:
        update_user_operation(
            reservation_operation["id"],
            {"status": "cancelled", "cancelled_at": int(time.time())},
        )
    sync_bot_user_amounts(user.id)

    await edit_message(
        query,
        "✅ تم الغاء الحجز واعادة المبلغ الى محفظتك.\n\n"
        f"المبلغ المعاد: {format_price(deposit)} ريال\n"
        f"رصيدك الحالي: {format_price(get_user_wallet(user.id))} ريال",
        reply_markup=back_keyboard(),
    )


async def buy_reserved_username(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    category_id: str,
    item_id: str,
) -> None:
    query = update.callback_query
    user = update.effective_user
    item = get_username_item(category_id, item_id)

    if not user:
        await edit_message(query, "⚠️ تعذر معرفة المستخدم. حاول مرة اخرى.")
        return

    remaining = get_active_payment_remaining_time(user.id)
    if remaining is not None and not is_admin(update) and not is_employee(update):
        time_str = format_remaining_time_arabic(remaining)
        await edit_message(
            query,
            "⚠️ لديك عملية دفع معلقة بالفعل.\n\n"
            "يرجى الانتظار حتى تنتهي صلاحيتها أو تكتمل قبل محاولة الشراء مرة أخرى.\n"
            f"الانتظار المتبقي: <b>{time_str}</b>.",
            reply_markup=back_keyboard(),
            parse_mode="HTML",
        )
        return

    if not item or item.get("status") != "reserved":
        await edit_message(query, "لا يوجد حجز نشط لهذا اليوزر.", reply_markup=back_keyboard())
        return

    reservation = item.get("reservation", {})
    if reservation.get("user_id") != user.id:
        await edit_message(query, "هذا الحجز ليس لك.", reply_markup=back_keyboard())
        return

    price = get_username_price(item)
    deposit = float(reservation.get("deposit", 0))
    remaining = max(price - deposit, 0)
    wallet = get_user_wallet(user.id)
    if wallet < remaining:
        await edit_message(
            query,
            "رصيدك غير كافي لاكمال الشراء.\n\n"
            f"المتبقي: {format_price(remaining)} ريال\n"
            f"رصيدك الحالي: {format_price(wallet)} ريال",
            reply_markup=username_reserved_keyboard(
                category_id,
                item_id,
                can_cancel=can_cancel_reservation(reservation),
            ),
        )
        return

    set_user_wallet(user.id, wallet - remaining)
    reservation_operation = find_user_operation_by_reservation(category_id, item_id)
    if reservation_operation:
        update_user_operation(
            reservation_operation["id"],
            {"status": "completed", "completed_at": int(time.time())},
        )
    item["status"] = "sold"
    item["sold_to"] = user.id
    item["sold_at"] = int(time.time())
    item.pop("reservation", None)
    order = add_purchase_operation(
        user_id=user.id,
        item_type="username",
        item_name=item.get("name", "يوزر بدون اسم"),
        amount=price,
        source="username_reservation",
        details={
            "category_id": category_id,
            "item_id": item_id,
            "deposit": deposit,
            "remaining_paid": remaining,
            "delivery": item.get("delivery", {}),
        },
    )
    archive_sold_username(category_id, item_id, item, order["order_number"], user.id)
    sync_bot_user_amounts(user.id)
    await notify_staff_about_order(context, user, order)

    await edit_message(
        query,
        "✅ تم اكمال شراء اليوزر بنجاح.\n\n"
        f"رقم الطلب: {order['order_number']}\n"
        f"اليوزر: {item.get('name', 'يوزر بدون اسم')}\n"
        f"المبلغ المخصوم الان: {format_price(remaining)} ريال\n"
        f"رصيدك الحالي: {format_price(get_user_wallet(user.id))} ريال",
        reply_markup=back_keyboard(),
    )
    await send_delivery_item(update, item.get("delivery", {}))


def format_admin_reservations() -> tuple[str, InlineKeyboardMarkup]:
    categories = get_username_categories()
    keyboard = []
    lines = ["الحجوزات الحالية:"]
    count = 0

    for category in categories:
        for item in category.get("items", []):
            if item.get("status") != "reserved":
                continue
            count += 1
            reservation = item.get("reservation", {})
            lines.append(
                f"\n{count}. {item.get('name', 'يوزر بدون اسم')}\n"
                f"القسم: {category.get('name', 'بدون اسم')}\n"
                f"ايدي العميل: {reservation.get('user_id')}\n"
                f"المبلغ المحجوز: {format_price(float(reservation.get('deposit', 0)))} ريال"
            )
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"🔓 تحرير حجز {item.get('name', 'يوزر')}",
                        callback_data=f"release_username:{category['id']}:{item['id']}",
                    )
                ]
            )

    if not count:
        return "📭 لا توجد حجوزات حاليا.", back_to_admin_usernames_keyboard()

    keyboard.append([InlineKeyboardButton("↩️ رجوع", callback_data="admin_usernames")])
    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


async def release_username_reservation(update: Update, category_id: str, item_id: str) -> None:
    query = update.callback_query
    item = get_username_item(category_id, item_id)
    if not item or item.get("status") != "reserved":
        await edit_message(
            query,
            "لا يوجد حجز نشط لهذا اليوزر.",
            reply_markup=back_to_admin_usernames_keyboard(),
        )
        return

    reservation = item.get("reservation", {})
    user_id = reservation.get("user_id")
    deposit = float(reservation.get("deposit", 0))
    if user_id:
        change_user_wallet(int(user_id), deposit)

    item["status"] = "available"
    item.pop("reservation", None)
    update_username_item(category_id, item_id, item)
    reservation_operation = find_user_operation_by_reservation(category_id, item_id)
    if reservation_operation:
        update_user_operation(
            reservation_operation["id"],
            {"status": "released_by_admin", "released_at": int(time.time())},
        )
    if user_id:
        sync_bot_user_amounts(int(user_id))

    await edit_message(
        query,
        "✅ تم تحرير الحجز واعادة المبلغ للعميل.\n\n"
        f"اليوزر: {item.get('name', 'يوزر بدون اسم')}\n"
        f"المبلغ المعاد: {format_price(deposit)} ريال",
        reply_markup=back_to_admin_usernames_keyboard(),
    )


async def edit_message(
    query,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
) -> None:
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except BadRequest as error:
        if "Message is not modified" in str(error):
            return
        raise


def format_order_customer(user) -> str:
    if not user:
        return "غير معروف"

    name = get_user_display_name(user)
    username = f"@{user.username}" if user.username else "لا يوجد"
    return f"{name} | {username} | {user.id}"


async def notify_staff_about_order(
    context: ContextTypes.DEFAULT_TYPE,
    user,
    order: dict,
) -> None:
    item_type_label = {
        "digital_product": "منتج رقمي",
        "username": "يوزر",
    }.get(order.get("item_type"), order.get("item_type", "غير معروف"))
    source_label = {
        "digital_products": "قسم المنتجات الرقمية",
        "usernames": "قسم اليوزرات",
        "username_reservation": "شراء حجز يوزر",
    }.get(order.get("source"), order.get("source", "غير معروف"))
    amount = format_price(parse_amount(order.get("amount", 0)))
    text = (
        "🛒 طلب جديد وصل.\n\n"
        f"🔖 رقم الطلب: {order.get('order_number', 'غير متوفر')}\n"
        f"📦 النوع: {item_type_label}\n"
        f"🏷️ القسم: {source_label}\n"
        f"📝 المنتج: {order.get('item_name', 'عنصر بدون اسم')}\n"
        f"💰 المبلغ: {amount} ريال\n"
        f"👤 العميل: {format_order_customer(user)}"
    )

    for staff_id in get_staff_ids():
        try:
            await context.bot.send_message(chat_id=staff_id, text=text)
        except Exception:
            LOGGER.exception(
                "Failed to notify staff %s about order %s",
                staff_id,
                order.get("order_number"),
            )


async def notify_admins_about_user_ban(
    context: ContextTypes.DEFAULT_TYPE,
    user,
    reason: str,
    attempts: list[dict],
) -> None:
    attempts_text = "\n".join(
        f"- {attempt.get('item_name', 'يوزر بدون اسم')} ({format_timestamp(attempt.get('created_at'))})"
        for attempt in attempts[-5:]
    ) or "لا توجد تفاصيل محاولات."
    text = (
        "🚫 تم حظر مستخدم تلقائيا.\n\n"
        f"👤 المستخدم: {format_order_customer(user)}\n"
        f"📌 السبب: {reason}\n"
        f"⏱️ الفترة: آخر {format_duration_arabic(USERNAME_ABUSE_WINDOW_SECONDS)}\n\n"
        "محاولات اليوزرات:\n"
        f"{attempts_text}"
    )

    for admin_id in get_admin_ids():
        try:
            await context.bot.send_message(chat_id=admin_id, text=text)
        except Exception:
            LOGGER.exception("Failed to notify admin %s about banned user %s", admin_id, getattr(user, "id", None))


async def notify_admins_about_startup_pending_usernames(bot, released_count: int, pending_items: list[dict]) -> None:
    if not released_count and not pending_items:
        return

    pending_text = "\n".join(
        (
            f"- {item.get('item_name', 'يوزر بدون اسم')} | "
            f"القسم: {item.get('category_name', 'بدون اسم')} | "
            f"المشتري: {item.get('user_id') or 'غير معروف'} | "
            f"المتبقي: {format_duration_arabic(int(item.get('remaining_seconds', 0) or 0))}"
        )
        for item in pending_items[:10]
    )
    if len(pending_items) > 10:
        pending_text += f"\n- وغيرها {len(pending_items) - 10} يوزر"
    if not pending_text:
        pending_text = "لا توجد يوزرات معلقة حاليا."

    text = (
        "🔎 فحص اليوزرات عند تشغيل البوت.\n\n"
        f"✅ تم إرجاع المنتهي: {released_count}\n"
        f"⏳ ما زال الشراء غير مكتمل: {len(pending_items)}\n\n"
        f"{pending_text}"
    )

    for admin_id in get_admin_ids():
        try:
            await bot.send_message(chat_id=admin_id, text=text)
        except Exception:
            LOGGER.exception("Failed to notify admin %s about startup pending usernames", admin_id)


async def notify_staff_about_ticket(
    context: ContextTypes.DEFAULT_TYPE,
    ticket: dict,
    title: str = "🎫 تذكرة دعم جديدة.",
    messages: list[dict] | None = None,
) -> None:
    text = (
        f"{title}\n\n"
        f"🔖 رقم التذكرة: {ticket.get('number')}\n"
        f"🏷️ النوع: {ticket.get('category_label')}\n"
        f"👤 العميل: {ticket.get('user_name')} ({ticket.get('user_id')})"
    )
    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📂 فتح التذكرة", callback_data=f"staff_ticket:{ticket['id']}")]]
    )
    for staff_id in get_staff_ids():
        try:
            await context.bot.send_message(chat_id=int(staff_id), text=text, reply_markup=reply_markup)
            for support_message in (messages or [])[-5:]:
                await send_support_message_to_user(
                    context,
                    int(staff_id),
                    support_message,
                    f"📨 رسالة داخل التذكرة {ticket.get('number')}:",
                )
        except Exception:
            LOGGER.exception("Failed to notify staff %s about ticket %s", staff_id, ticket.get("id"))


async def send_support_message_to_user(context: ContextTypes.DEFAULT_TYPE, user_id: int, message: dict, prefix: str) -> None:
    message_type = message.get("type")
    caption = prefix
    if message.get("caption"):
        caption += f"\n\n{message.get('caption')}"
    try:
        if message_type == "text":
            await context.bot.send_message(chat_id=user_id, text=f"{prefix}\n\n{message.get('text', '')}")
        elif message_type == "photo":
            await context.bot.send_photo(chat_id=user_id, photo=message.get("file_id"), caption=caption)
        elif message_type == "document":
            await context.bot.send_document(chat_id=user_id, document=message.get("file_id"), caption=caption)
        elif message_type == "video":
            await context.bot.send_video(chat_id=user_id, video=message.get("file_id"), caption=caption)
    except Exception:
        LOGGER.exception("Failed to send support message to user %s", user_id)


async def start_support_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    register_bot_user(update.effective_user)

    if not await ensure_required_channel_subscription(update, context):
        return ConversationHandler.END

    category = query.data.split(":", 1)[1]
    context.user_data["support_category"] = category
    context.user_data["support_messages"] = []
    context.user_data.pop("support_ticket_id", None)

    await edit_message(
        query,
        "🎫 فتح تذكرة دعم.\n\n"
        f"🏷️ النوع: {SUPPORT_CATEGORIES.get(category, 'دعم')}\n\n"
        "📨 ارسل شرح المشكلة، ويمكنك ارسال صور او ملفات ايضا.\n"
        "بعد ما تكمل، اضغط زر إنشاء التذكرة.",
        reply_markup=support_collect_keyboard(),
    )
    return SUPPORT_MESSAGE


async def start_add_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not await ensure_required_channel_subscription(update, context):
        return ConversationHandler.END

    ticket_id = query.data.split(":", 1)[1]
    ticket = get_ticket(ticket_id)
    if not ticket or ticket.get("user_id") != query.from_user.id:
        await edit_message(query, "❌ التذكرة غير موجودة.", reply_markup=support_keyboard())
        return ConversationHandler.END
    if ticket.get("status") == "closed":
        await edit_message(query, "🔒 هذه التذكرة مغلقة ولا يمكن إضافة رد.", reply_markup=user_ticket_keyboard(ticket))
        return ConversationHandler.END

    context.user_data["support_ticket_id"] = ticket_id
    context.user_data["support_messages"] = []
    context.user_data.pop("support_category", None)
    await edit_message(
        query,
        f"➕ إضافة رد على التذكرة {ticket.get('number')}.\n\n"
        "📨 ارسل ردك نصا او صورة او ملف، ثم اضغط إرسال.",
        reply_markup=support_collect_keyboard(),
    )
    return SUPPORT_MESSAGE


async def receive_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_required_channel_subscription(update, context):
        return ConversationHandler.END

    user = update.effective_user
    message = build_support_message(update.message, get_actor_info(user, "customer"))
    if not message:
        await update.message.reply_text("📨 ارسل نص، صورة، ملف، او فيديو فقط.")
        return SUPPORT_MESSAGE

    context.user_data.setdefault("support_messages", []).append(message)
    count = len(context.user_data["support_messages"])
    await update.message.reply_text(
        f"✅ تم استلام الرسالة رقم {count}.\n\n"
        "📨 يمكنك ارسال المزيد، أو اضغط إنشاء التذكرة / إرسال.",
        reply_markup=support_collect_keyboard(),
    )
    return SUPPORT_MESSAGE


async def finish_support_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not await ensure_required_channel_subscription(update, context):
        return ConversationHandler.END

    user = update.effective_user
    messages = context.user_data.get("support_messages", [])
    if not messages:
        await edit_message(query, "⚠️ ارسل رسالة واحدة على الأقل قبل إنشاء التذكرة.", reply_markup=support_collect_keyboard())
        return SUPPORT_MESSAGE

    ticket_id = context.user_data.pop("support_ticket_id", None)
    if ticket_id:
        ticket = get_ticket(ticket_id)
        if not ticket or ticket.get("user_id") != user.id:
            await edit_message(query, "❌ التذكرة غير موجودة.", reply_markup=support_keyboard())
            return ConversationHandler.END
        for message in messages:
            ticket = add_ticket_message(ticket_id, message) or ticket
        context.user_data.pop("support_messages", None)
        await notify_staff_about_ticket(context, ticket, "💬 رد جديد من العميل.", messages)
        await edit_message(query, "✅ تم إرسال ردك داخل التذكرة.", reply_markup=user_ticket_keyboard(ticket))
        return ConversationHandler.END

    category = context.user_data.pop("support_category", "other")
    ticket = create_support_ticket(user, category, messages)
    context.user_data.pop("support_messages", None)
    await notify_staff_about_ticket(context, ticket, messages=messages)
    await edit_message(
        query,
        "✅ تم إنشاء تذكرتك بنجاح.\n\n"
        f"🔖 رقم التذكرة: {ticket.get('number')}\n"
        "سيتم الرد عليك من فريق الدعم قريبا.",
        reply_markup=user_ticket_keyboard(ticket),
    )
    return ConversationHandler.END


async def cancel_support_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("support_category", None)
    context.user_data.pop("support_messages", None)
    context.user_data.pop("support_ticket_id", None)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await edit_message(query, "❌ تم إلغاء العملية.", reply_markup=support_keyboard())
    else:
        await update.message.reply_text("❌ تم إلغاء العملية.", reply_markup=support_keyboard())
    return ConversationHandler.END


async def start_staff_ticket_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not (is_admin(update) or is_employee(update)):
        await edit_message(query, "🔒 هذه القائمة مخصصة للادمن والموظفين فقط.")
        return ConversationHandler.END

    ticket_id = query.data.split(":", 1)[1]
    ticket = get_ticket(ticket_id)
    if not ticket:
        await edit_message(query, "❌ التذكرة غير موجودة.", reply_markup=staff_tickets_keyboard())
        return ConversationHandler.END
    if ticket.get("status") == "closed":
        await edit_message(query, "🔒 هذه التذكرة مغلقة.", reply_markup=staff_ticket_keyboard(ticket))
        return ConversationHandler.END

    context.user_data["staff_reply_ticket_id"] = ticket_id
    await edit_message(
        query,
        f"✍️ الرد على التذكرة {ticket.get('number')}.\n\n"
        "📨 ارسل الرد نصا او صورة او ملف.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ الغاء", callback_data="cancel_staff_ticket_reply")]]),
    )
    return SUPPORT_REPLY_MESSAGE


async def receive_staff_ticket_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not (is_admin(update) or is_employee(update)):
        await update.message.reply_text("🔒 هذه القائمة مخصصة للادمن والموظفين فقط.")
        return ConversationHandler.END

    ticket_id = context.user_data.pop("staff_reply_ticket_id", None)
    ticket = get_ticket(ticket_id) if ticket_id else None
    if not ticket:
        await update.message.reply_text("❌ التذكرة غير موجودة.", reply_markup=staff_tickets_keyboard())
        return ConversationHandler.END

    role = "admin" if is_admin(update) else "employee"
    message = build_support_message(update.message, get_actor_info(update.effective_user, role))
    if not message:
        await update.message.reply_text("📨 ارسل نص، صورة، ملف، او فيديو فقط.")
        context.user_data["staff_reply_ticket_id"] = ticket_id
        return SUPPORT_REPLY_MESSAGE

    ticket = add_ticket_message(ticket_id, message) or ticket
    await send_support_message_to_user(
        context,
        int(ticket["user_id"]),
        message,
        f"💬 رد الدعم على التذكرة {ticket.get('number')}:",
    )
    await update.message.reply_text("✅ تم إرسال الرد للعميل.", reply_markup=staff_ticket_keyboard(ticket))
    return ConversationHandler.END


async def cancel_staff_ticket_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("staff_reply_ticket_id", None)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await edit_message(query, "❌ تم إلغاء الرد.", reply_markup=staff_tickets_keyboard())
    else:
        await update.message.reply_text("❌ تم إلغاء الرد.", reply_markup=staff_tickets_keyboard())
    return ConversationHandler.END


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    await query.answer()

    if query.data.startswith("direct_pay_method:"):
        parts = query.data.split(":")
        method = parts[1]
        payment_id = parts[2]
        await process_direct_payment_method(update, context, method, payment_id)
        return

    if query.data.startswith("direct_pay_cancel:"):
        payment_id = query.data.split(":")[1]
        await process_direct_payment_cancel(update, context, payment_id)
        return

    if user and is_user_banned(user.id) and not (is_admin(update) or is_employee(update)):
        await edit_message(query, "🚫 حسابك محظور من استخدام البوت.")
        return

    if query.data == "check_required_channel":
        if not await ensure_required_channel_subscription(update, context):
            return

        await edit_message(
            query,
            WELCOME_MESSAGE,
            reply_markup=main_menu_keyboard(
                show_admin=is_admin(update),
                show_employee=is_employee(update),
            ),
        )
        return

    admin_callbacks = (
        "admin_",
        "staff_",
        "employee_",
        "release_username:",
    )
    if (
        not query.data.startswith(admin_callbacks)
        and query.data not in {"admin_menu", "main_menu"}
        and not await ensure_required_channel_subscription(update, context)
    ):
        return

    if query.data == "main_menu":
        if not await ensure_required_channel_subscription(update, context):
            return

        await edit_message(
            query,
            WELCOME_MESSAGE,
            reply_markup=main_menu_keyboard(
                show_admin=is_admin(update),
                show_employee=is_employee(update),
            ),
        )
        return

    if query.data == "admin_menu":
        if not is_admin(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للادمن فقط.")
            return

        await edit_message(
            query,
            "لوحة الادمن.\n\n"
            "👇 اختر العملية التي تريد تنفيذها:",
            reply_markup=admin_keyboard(),
        )
        return

    if query.data == "admin_stats":
        if not is_admin(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للادمن فقط.")
            return

        stats_text = format_admin_statistics()
        await edit_message(
            query,
            stats_text,
            reply_markup=admin_stats_keyboard(),
            parse_mode="HTML",
        )
        return

    if query.data == "admin_reset_sales_stats":
        if not is_admin(update):
            await edit_message(query, "🔒 هذه العملية مخصصة للادمن فقط.")
            return

        settings = load_bot_settings()
        settings["sales_stats_reset_time"] = int(time.time())
        save_bot_settings(settings)
        
        try:
            await query.answer("✅ تم تصفير إحصائيات المبيعات!")
        except Exception:
            pass

        stats_text = format_admin_statistics()
        await edit_message(
            query,
            stats_text,
            reply_markup=admin_stats_keyboard(),
            parse_mode="HTML",
        )
        return

    if query.data == "admin_payment_settings":
        if not is_admin(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للادمن فقط.")
            return

        await edit_message(
            query,
            format_payment_settings_overview(),
            reply_markup=admin_payment_settings_keyboard(),
            parse_mode="HTML",
        )
        return

    if query.data == "admin_nowpayments_menu":
        if not is_admin(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للادمن فقط.")
            return

        await edit_message(
            query,
            format_nowpayments_settings(),
            reply_markup=admin_nowpayments_keyboard(),
            parse_mode="HTML",
        )
        return

    if query.data == "admin_tap_menu":
        if not is_admin(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للادمن فقط.")
            return

        await edit_message(
            query,
            format_tap_settings(),
            reply_markup=admin_tap_keyboard(),
            parse_mode="HTML",
        )
        return

    if query.data == "admin_toggle_nowpayments":
        if not is_admin(update):
            await edit_message(query, "🔒 هذه العملية مخصصة للادمن فقط.")
            return

        new_state = not is_nowpayments_enabled()
        save_payment_setting("nowpayments_enabled", new_state)
        status_msg = "مفعّلة" if new_state else "معطّلة"
        try:
            await query.answer(f"✅ تم تغيير حالة NOWPayments إلى: {status_msg}")
        except Exception:
            pass

        await edit_message(
            query,
            format_nowpayments_settings(),
            reply_markup=admin_nowpayments_keyboard(),
            parse_mode="HTML",
        )
        return

    if query.data == "admin_toggle_tap":
        if not is_admin(update):
            await edit_message(query, "🔒 هذه العملية مخصصة للادمن فقط.")
            return

        new_state = not is_tap_enabled()
        save_payment_setting("tap_enabled", new_state)
        status_msg = "مفعّلة" if new_state else "معطّلة"
        try:
            await query.answer(f"✅ تم تغيير حالة Tap Payments إلى: {status_msg}")
        except Exception:
            pass

        await edit_message(
            query,
            format_tap_settings(),
            reply_markup=admin_tap_keyboard(),
            parse_mode="HTML",
        )
        return

    if query.data == "admin_required_channel":
        if not is_admin(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للادمن فقط.")
            return

        await edit_message(
            query,
            format_required_channel_settings(),
            reply_markup=required_channel_admin_keyboard(),
        )
        return

    if query.data == "admin_clear_required_channel":
        if not is_admin(update):
            await edit_message(query, "🔒 هذه العملية مخصصة للادمن فقط.")
            return

        settings = load_bot_settings()
        settings["required_channel"] = None
        save_bot_settings(settings)
        await edit_message(
            query,
            "✅ تم تعطيل الاشتراك الاجباري.",
            reply_markup=required_channel_admin_keyboard(),
        )
        return

    if query.data == "admin_employees":
        if not is_admin(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للادمن فقط.")
            return

        await edit_message(
            query,
            "إدارة الموظفين.\n\n"
            "👇 اختر العملية التي تريد تنفيذها:",
            reply_markup=admin_employees_keyboard(),
        )
        return

    if query.data == "admin_show_employees":
        if not is_admin(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للادمن فقط.")
            return

        employees = load_employees().get("employees", [])
        if not employees:
            await edit_message(
                query,
                "لا يوجد موظفين حاليا.",
                reply_markup=admin_employees_keyboard(),
            )
            return

        await edit_message(
            query,
            "الموظفين.\n\n"
            "👇 اختر موظف لعرض الاحصائيات او الحذف:",
            reply_markup=employees_keyboard(),
        )
        return

    if query.data.startswith("admin_employee:"):
        if not is_admin(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للادمن فقط.")
            return

        employee_id = int(query.data.split(":", 1)[1])
        employee = get_employee(employee_id)
        if not employee:
            await edit_message(
                query,
                "الموظف غير موجود.",
                reply_markup=admin_employees_keyboard(),
            )
            return

        await edit_message(
            query,
            format_employee_details(employee),
            reply_markup=employee_details_keyboard(employee_id),
        )
        return

    if query.data.startswith("admin_delete_employee:"):
        if not is_admin(update):
            await edit_message(query, "🔒 هذه العملية مخصصة للادمن فقط.")
            return

        employee_id = int(query.data.split(":", 1)[1])
        deleted_employee = delete_employee(employee_id)
        if not deleted_employee:
            await edit_message(
                query,
                "الموظف غير موجود.",
                reply_markup=admin_employees_keyboard(),
            )
            return

        await edit_message(
            query,
            "✅ تم حذف الموظف بنجاح.\n\n"
            f"الموظف: {employee_display_name(deleted_employee)}",
            reply_markup=admin_employees_keyboard(),
        )
        return

    if query.data == "employee_menu":
        if not is_employee(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للموظفين فقط.")
            return

        await edit_message(
            query,
            "لوحة الموظف.\n\n"
            "👇 اختر العملية التي تريد تنفيذها:",
            reply_markup=employee_keyboard(),
        )
        return

    if query.data == "employee_products":
        if not is_employee(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للموظفين فقط.")
            return

        products = ensure_product_ids(load_products())
        if not products:
            await edit_message(
                query,
                "📭 لا توجد منتجات حاليا.",
                reply_markup=employee_keyboard(),
            )
            return

        await edit_message(
            query,
            "👇 اختر المنتج الذي تريد اضافة مخزون له:",
            reply_markup=employee_products_keyboard(products),
        )
        return

    if query.data == "employee_username_categories":
        if not is_employee(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للموظفين فقط.")
            return

        categories = get_username_categories()
        if not categories:
            await edit_message(
                query,
                "📭 لا توجد اقسام يوزرات حاليا.",
                reply_markup=employee_keyboard(),
            )
            return

        await edit_message(
            query,
            "👇 اختر القسم الذي تريد اضافة يوزر داخله:",
            reply_markup=employee_username_categories_keyboard(categories),
        )
        return

    if query.data.startswith("employee_username_category:"):
        if not is_employee(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للموظفين فقط.")
            return

        category_id = query.data.split(":", 1)[1]
        category = get_username_category(category_id)
        if not category:
            await edit_message(
                query,
                "القسم غير موجود.",
                reply_markup=employee_username_categories_keyboard(get_username_categories()),
            )
            return

        await edit_message(
            query,
            f"قسم: {category.get('name', 'بدون اسم')}\n\n"
            "يمكنك اضافة يوزر جديد داخل هذا القسم.",
            reply_markup=employee_username_category_keyboard(category_id),
        )
        return

    if query.data == "admin_show_products":
        if not is_admin(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للادمن فقط.")
            return

        text, reply_markup = format_admin_products()
        await edit_message(query, text, reply_markup=reply_markup)
        return

    if query.data == "admin_usernames":
        if not is_admin(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للادمن فقط.")
            return

        await edit_message(
            query,
            "قسم اليوزرات.\n\n"
            "👇 اختر العملية التي تريد تنفيذها:",
            reply_markup=admin_usernames_keyboard(),
        )
        return

    if query.data == "admin_username_categories":
        if not is_admin(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للادمن فقط.")
            return

        categories = get_username_categories()
        if not categories:
            await edit_message(
                query,
                "📭 لا توجد اقسام يوزرات حاليا.\n\nاضف قسم جديد اولا.",
                reply_markup=back_to_admin_usernames_keyboard(),
            )
            return

        await edit_message(
            query,
            "👇 اختر القسم الذي تريد ادارته:",
            reply_markup=username_categories_keyboard(categories, "admin_username_category"),
        )
        return

    if query.data.startswith("admin_username_category:"):
        if not is_admin(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للادمن فقط.")
            return

        category_id = query.data.split(":", 1)[1]
        category = get_username_category(category_id)
        if not category:
            await edit_message(
                query,
                "القسم غير موجود.",
                reply_markup=back_to_admin_username_categories_keyboard(),
            )
            return

        await edit_message(
            query,
            f"قسم: {category.get('name', 'بدون اسم')}\n\n"
            f"عدد اليوزرات: {len(category.get('items', []))}",
            reply_markup=admin_username_category_keyboard(category_id),
        )
        return

    if query.data.startswith("admin_show_usernames:"):
        if not is_admin(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للادمن فقط.")
            return

        category_id = query.data.split(":", 1)[1]
        category = get_username_category(category_id)
        if not category:
            await edit_message(
                query,
                "القسم غير موجود.",
                reply_markup=back_to_admin_username_categories_keyboard(),
            )
            return

        items = category.get("items", [])
        if not items:
            await edit_message(
                query,
                f"📁 قسم {category.get('name', 'بدون اسم')}.\n\n📭 لا توجد يوزرات في هذا القسم حالياً.",
                reply_markup=admin_username_category_keyboard(category_id),
            )
            return

        await edit_message(
            query,
            f"📁 قسم {category.get('name', 'بدون اسم')}.\n\n🟢 = متاح | 🟡 = محجوز\n👇 اختر اليوزر لإدارته أو حذفه:",
            reply_markup=admin_usernames_items_keyboard(category),
        )
        return

    if query.data.startswith("admin_username_item:"):
        if not is_admin(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للادمن فقط.")
            return

        _, category_id, item_id = query.data.split(":", 2)
        category = get_username_category(category_id)
        item = get_username_item(category_id, item_id)
        if not category:
            await edit_message(query, "القسم غير موجود.", reply_markup=back_to_admin_username_categories_keyboard())
            return
        if not item:
            await edit_message(
                query,
                "هذا اليوزر غير موجود.",
                reply_markup=admin_username_category_keyboard(category_id),
            )
            return

        await edit_message(
            query,
            format_admin_username_item(category, item),
            reply_markup=admin_username_item_details_keyboard(category_id, item_id),
            parse_mode="HTML",
        )
        return

    if query.data.startswith("admin_delete_username_item:"):
        if not is_admin(update):
            await edit_message(query, "🔒 هذه العملية مخصصة للادمن فقط.")
            return

        _, category_id, item_id = query.data.split(":", 2)
        deleted_item = delete_username_item(category_id, item_id)
        if not deleted_item:
            await edit_message(
                query,
                "اليوزر غير موجود أو تم حذفه مسبقاً.",
                reply_markup=admin_username_category_keyboard(category_id),
            )
            return

        await edit_message(
            query,
            "✅ تم حذف اليوزر بنجاح من داخل المتجر.\n\n"
            f"اليوزر: {deleted_item.get('name', 'يوزر بدون اسم')}",
            reply_markup=admin_username_category_keyboard(category_id),
        )
        return

    if query.data == "admin_username_reservations":
        if not is_admin(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للادمن فقط.")
            return

        text, reply_markup = format_admin_reservations()
        await edit_message(query, text, reply_markup=reply_markup)
        return

    if query.data.startswith("admin_delete_username_category:"):
        if not is_admin(update):
            await edit_message(query, "🔒 هذه العملية مخصصة للادمن فقط.")
            return

        category_id = query.data.split(":", 1)[1]
        deleted_category = delete_username_category(category_id)
        if not deleted_category:
            await edit_message(
                query,
                "القسم غير موجود.",
                reply_markup=back_to_admin_username_categories_keyboard(),
            )
            return

        await edit_message(
            query,
            "✅ تم حذف القسم بنجاح.\n\n"
            f"القسم: {deleted_category.get('name', 'قسم بدون اسم')}\n"
            f"عدد اليوزرات المحذوفة: {len(deleted_category.get('items', []))}",
            reply_markup=admin_usernames_keyboard(),
        )
        return

    if query.data.startswith("release_username:"):
        if not is_admin(update):
            await edit_message(query, "🔒 هذه العملية مخصصة للادمن فقط.")
            return

        _, category_id, item_id = query.data.split(":", 2)
        await release_username_reservation(update, category_id, item_id)
        return

    if query.data.startswith("admin_delete_product:"):
        if not is_admin(update):
            await edit_message(query, "🔒 هذه العملية مخصصة للادمن فقط.")
            return

        product_id = query.data.split(":", 1)[1]
        deleted_product = delete_product(product_id)
        if not deleted_product:
            await edit_message(
                query,
                "المنتج غير موجود.",
                reply_markup=back_to_admin_products_keyboard(),
            )
            return

        await edit_message(
            query,
            "✅ تم حذف المنتج بنجاح.\n\n"
            f"المنتج: {deleted_product.get('name', 'منتج بدون اسم')}",
            reply_markup=admin_keyboard(),
        )
        return

    if query.data.startswith("admin_product:"):
        if not is_admin(update):
            await edit_message(query, "🔒 هذه القائمة مخصصة للادمن فقط.")
            return

        product_id = query.data.split(":", 1)[1]
        product = get_product(product_id)
        if not product:
            await edit_message(
                query,
                "المنتج غير موجود.",
                reply_markup=back_to_admin_products_keyboard(),
            )
            return

        await edit_message(
            query,
            format_product_details(product),
            reply_markup=product_admin_keyboard(product_id),
        )
        return

    if query.data == "digital_products":
        text, reply_markup = format_products_menu()
        await edit_message(
            query,
            text,
            reply_markup=reply_markup,
        )
        return

    if query.data == "usernames":
        text, reply_markup = format_usernames_categories()
        await edit_message(query, text, reply_markup=reply_markup)
        return

    if query.data.startswith("username_category:"):
        category_id = query.data.split(":", 1)[1]
        category = get_username_category(category_id)
        if not category:
            await edit_message(query, "القسم غير موجود.", reply_markup=back_keyboard())
            return

        text, reply_markup = format_username_category(category)
        await edit_message(query, text, reply_markup=reply_markup)
        return

    if query.data.startswith("username_item:"):
        _, category_id, item_id = query.data.split(":", 2)
        release_expired_username_pending_payments()
        category = get_username_category(category_id)
        item = get_username_item(category_id, item_id)
        if not category:
            await edit_message(query, "القسم غير موجود.", reply_markup=back_keyboard())
            return
        if not item or item.get("status", "available") != "available":
            await edit_message(
                query,
                "هذا اليوزر لم يعد متاحا.",
                reply_markup=back_to_username_categories_keyboard(),
            )
            return

        await edit_message(
            query,
            format_username_item(category, item),
            reply_markup=username_purchase_keyboard(category_id, item_id),
        )
        return

    if query.data.startswith("buy_username:"):
        _, category_id, item_id = query.data.split(":", 2)
        await buy_username_item(update, context, category_id, item_id)
        return

    if query.data.startswith("reserve_username:"):
        await edit_message(
            query,
            "تم إلغاء الحجز.\n\n"
            "الشراء صار فوري ومباشر من زر الشراء.",
            reply_markup=back_keyboard(),
        )
        return

    if query.data.startswith("cancel_username_reservation:"):
        _, category_id, item_id = query.data.split(":", 2)
        await cancel_username_reservation(update, category_id, item_id)
        return

    if query.data.startswith("buy_reserved_username:"):
        await edit_message(
            query,
            "تم إلغاء الشراء عبر المحفظة للحجوزات.\n\n"
            "استخدم الشراء المباشر من المنتجات المتاحة، أو تواصل مع الدعم لو عندك حجز قديم.",
            reply_markup=back_keyboard(),
        )
        return

    if query.data.startswith("product:"):
        product_id = query.data.split(":", 1)[1]
        product = get_product(product_id)
        if not product:
            await edit_message(
                query,
                "هذا المنتج لم يعد متاحا.",
                reply_markup=back_to_products_keyboard(),
            )
            return
        if not get_delivery_items(product):
            await edit_message(
                query,
                "📭 هذا المنتج غير متوفر حاليا.",
                reply_markup=back_to_products_keyboard(),
            )
            return

        await edit_message(
            query,
            format_product_purchase(product),
            reply_markup=product_purchase_keyboard(product_id),
        )
        return

    if query.data.startswith("buy:"):
        product_id = query.data.split(":", 1)[1]
        await buy_product(update, context, product_id)
        return

    if query.data == "wallet":
        await edit_message(
            query,
            "تم إلغاء المحفظة.\n\n"
            "الشراء صار مباشر: اختر المنتج واضغط شراء، وبيطلع لك رابط الدفع مباشرة.",
            reply_markup=back_keyboard(),
        )
        return

    if query.data == "add_wallet_funds":
        await edit_message(
            query,
            "تم إلغاء شحن المحفظة.\n\n"
            "ادفع مباشرة عند شراء المنتج.",
            reply_markup=back_keyboard(),
        )
        return

    if query.data.startswith("check_topup:"):
        await edit_message(
            query,
            "طريقة الدفع القديمة غير متاحة حاليا. استخدم الشراء المباشر من صفحة المنتج.",
            reply_markup=back_keyboard(),
        )
        return

    if query.data == "operations" or query.data.startswith("operations:"):
        user = update.effective_user
        view = "all"
        page = 0
        if ":" in query.data:
            parts = query.data.split(":")
            view = parts[1]
            if len(parts) > 2:
                try:
                    page = max(0, int(parts[2]))
                except ValueError:
                    page = 0
        if user and view == "purchases":
            purchases = get_user_purchase_operations(user.id)
            await edit_message(
                query,
                "المشتريات.\n\nاختر عملية الشراء التي تريد عرض تفاصيلها:"
                if purchases
                else "المشتريات.\n\nلا توجد مشتريات حتى الان.",
                reply_markup=purchases_keyboard(user.id, page),
            )
            return
        await edit_message(
            query,
            format_user_operations(user.id, view) if user else "⚠️ تعذر معرفة المستخدم.",
            reply_markup=operations_keyboard(user.id, view) if user else back_keyboard(),
        )
        return

    if query.data.startswith("operation_purchase:"):
        user = update.effective_user
        operation_id = query.data.split(":", 1)[1]
        operation = get_user_operation(operation_id)
        if (
            not user
            or not operation
            or operation.get("user_id") != user.id
            or operation.get("type") != "purchase"
        ):
            await edit_message(query, "عملية الشراء غير موجودة.", reply_markup=operations_keyboard(user.id) if user else back_keyboard())
            return

        delivery = get_purchase_delivery_item(operation)
        await edit_message(
            query,
            format_purchase_details(operation),
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("↩️ رجوع للمشتريات", callback_data="operations:purchases")],
                    [InlineKeyboardButton("🏠 العودة للقائمة الرئيسية", callback_data="main_menu")],
                ]
            ),
        )
        if delivery:
            delivery_type = delivery.get("type")
            caption = format_purchase_delivery_caption(operation)
            if delivery_type == "document":
                await query.message.reply_document(
                    document=delivery.get("file_id"),
                    caption=caption,
                )
            elif delivery_type == "video":
                await query.message.reply_video(
                    video=delivery.get("file_id"),
                    caption=caption,
                )
        return

    if query.data == "support":
        await edit_message(
            query,
            "🤝 مركز المساعدة والدعم.\n\n"
            "🎫 اختر نوع المشكلة لفتح تذكرة جديدة، أو راجع تذاكرك السابقة من نفس القائمة.",
            reply_markup=support_keyboard(),
        )
        return

    if query.data == "support_my_tickets":
        await edit_message(
            query,
            "🎫 تذاكري.\n\n"
            "اختر التذكرة التي تريد مراجعتها أو إضافة رد عليها.",
            reply_markup=user_tickets_keyboard(user.id),
        )
        return

    if query.data.startswith("support_ticket:"):
        ticket_id = query.data.split(":", 1)[1]
        ticket = get_ticket(ticket_id)
        if not ticket or ticket.get("user_id") != user.id:
            await edit_message(query, "❌ التذكرة غير موجودة.", reply_markup=support_keyboard())
            return
        await edit_message(query, format_ticket(ticket), reply_markup=user_ticket_keyboard(ticket))
        return

    if query.data == "staff_tickets":
        if not (is_admin(update) or is_employee(update)):
            await edit_message(query, "🔒 هذه القائمة مخصصة للادمن والموظفين فقط.")
            return
        await edit_message(
            query,
            "🎫 تذاكر الدعم.\n\n"
            "اختر تذكرة لعرض التفاصيل والرد أو الإغلاق.",
            reply_markup=staff_tickets_keyboard(),
        )
        return

    if query.data.startswith("staff_ticket_close:"):
        if not (is_admin(update) or is_employee(update)):
            await edit_message(query, "🔒 هذه القائمة مخصصة للادمن والموظفين فقط.")
            return
        ticket_id = query.data.split(":", 1)[1]
        ticket = get_ticket(ticket_id)
        if not ticket:
            await edit_message(query, "❌ التذكرة غير موجودة.", reply_markup=staff_tickets_keyboard())
            return
        role = "admin" if is_admin(update) else "employee"
        actor = get_actor_info(user, role)
        update_ticket(
            ticket_id,
            {
                "status": "closed",
                "closed_at": int(time.time()),
                "closed_by": actor,
                "updated_at": int(time.time()),
            },
        )
        ticket = get_ticket(ticket_id) or ticket
        try:
            await context.bot.send_message(
                chat_id=int(ticket["user_id"]),
                text=f"🔒 تم إغلاق تذكرتك رقم {ticket.get('number')} من فريق الدعم.",
                reply_markup=support_keyboard(),
            )
        except Exception:
            LOGGER.exception("Failed to notify user about closed ticket %s", ticket_id)
        await edit_message(query, "✅ تم إغلاق التذكرة.", reply_markup=staff_ticket_keyboard(ticket))
        return

    if query.data.startswith("staff_ticket:"):
        if not (is_admin(update) or is_employee(update)):
            await edit_message(query, "🔒 هذه القائمة مخصصة للادمن والموظفين فقط.")
            return
        ticket_id = query.data.split(":", 1)[1]
        ticket = get_ticket(ticket_id)
        if not ticket:
            await edit_message(query, "❌ التذكرة غير موجودة.", reply_markup=staff_tickets_keyboard())
            return
        await edit_message(query, format_ticket(ticket, for_staff=True), reply_markup=staff_ticket_keyboard(ticket))
        return

    LOGGER.warning("Unknown callback data: %s", query.data)


async def auto_check_topups(bot) -> None:
    now = int(time.time())
    release_expired_username_pending_payments(now)
    for topup in load_topups().get("topups", []):
        expired_now = expire_topup_if_needed(topup, now)
        if expired_now and topup.get("kind") == "direct_purchase":
            release_direct_purchase_hold(topup)
        needs_link_hide = (
            str(topup.get("payment_status") or "").lower() == "expired"
            and is_topup_expired(topup, now)
            and not topup.get("payment_link_hidden_at")
        )
        if not expired_now and not needs_link_hide:
            continue

        chat_id = topup.get("payment_message_chat_id")
        message_id = topup.get("payment_message_id")
        if not chat_id or not message_id:
            update_topup_by_id(str(topup["id"]), {"payment_link_hidden_at": int(time.time())})
            continue

        try:
            await bot.edit_message_text(
                chat_id=int(chat_id),
                message_id=int(message_id),
                text=(
                    "⏱️ انتهت صلاحية رابط الدفع.\n\n"
                    "تم إيقاف طريقة الدفع لهذه العملية. ابدأ طلب شراء جديد إذا ما زلت ترغب بالمنتج."
                ),
                reply_markup=back_keyboard(),
            )
            update_topup_by_id(str(topup["id"]), {"payment_link_hidden_at": int(time.time())})
        except BadRequest:
            LOGGER.info("Could not edit expired topup payment message %s", topup.get("id"))
            update_topup_by_id(str(topup["id"]), {"payment_link_hidden_at": int(time.time())})
        except Exception:
            LOGGER.exception("Failed to hide expired topup payment link %s", topup.get("id"))

    for topup in get_pending_invoice_topups():
        topup_id = str(topup["id"])
        try:
            verified_payment = get_verified_topup_payment(topup)
        except Exception as error:
            LOGGER.warning(
                "Failed to auto-check topup %s invoice %s: %s",
                topup_id,
                topup.get("invoice_id"),
                error,
            )
            continue

        if not verified_payment:
            continue

        status, payment = verified_payment
        fresh_topup = get_topup_by_id(topup_id)
        if not fresh_topup or fresh_topup.get("credited"):
            continue

        if fresh_topup.get("kind") == "direct_purchase":
            await fulfill_direct_purchase_payment(bot, fresh_topup, payment)
            continue

        credit_amount = parse_amount(fresh_topup.get("credit_amount", fresh_topup.get("amount", 0)))
        change_user_wallet(int(fresh_topup["user_id"]), credit_amount)
        updates = {
            "payment_status": status,
            "credited": True,
            "credited_at": int(time.time()),
            "raw_status": payment,
        }
        if payment.get("payment_id"):
            updates["payment_id"] = payment.get("payment_id")
        update_topup_by_id(topup_id, updates)

        try:
            await bot.send_message(
                chat_id=int(fresh_topup["user_id"]),
                text=(
                    "✅ تم تأكيد الدفع وإضافة الرصيد بنجاح.\n\n"
                    f"المبلغ المضاف: {format_price(credit_amount)}"
                ),
                reply_markup=back_keyboard(),
            )
        except Exception:
            LOGGER.exception("Failed to notify user about credited topup %s", topup_id)


async def auto_check_topups_loop(app: Application) -> None:
    while True:
        await asyncio.sleep(10)
        try:
            await auto_check_topups(app.bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("Auto topup checker crashed")


async def start_background_tasks(app: Application) -> None:
    try:
        now = int(time.time())
        released_count = release_expired_username_pending_payments(now)
        pending_items = get_pending_username_payment_items(now)
        await notify_admins_about_startup_pending_usernames(app.bot, released_count, pending_items)
        await auto_check_topups(app.bot)
    except Exception:
        LOGGER.exception("Startup username pending payment check failed")

    app.bot_data["auto_check_topups_task"] = asyncio.create_task(auto_check_topups_loop(app))


async def stop_background_tasks(app: Application) -> None:
    task = app.bot_data.get("auto_check_topups_task")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def main() -> None:
    setup_initial_env_if_missing()

    token = os.getenv(TOKEN_ENV_NAME)
    if not token:
        raise RuntimeError(
            f"Missing {TOKEN_ENV_NAME}. Add it to {ENV_FILE} before running the bot."
        )

    app = (
        Application.builder()
        .token(token)
        .post_init(start_background_tasks)
        .post_shutdown(stop_background_tasks)
        .build()
    )
    add_product_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_add_product, pattern="^admin_add_product$"),
        ],
        states={
            PRODUCT_NAME: [
                CallbackQueryHandler(cancel_add_product, pattern="^cancel_add_product$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_product_name),
            ],
            PRODUCT_DESCRIPTION: [
                CallbackQueryHandler(cancel_add_product, pattern="^cancel_add_product$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_product_description),
            ],
            PRODUCT_PRICE: [
                CallbackQueryHandler(cancel_add_product, pattern="^cancel_add_product$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_product_price),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_add_product),
            CallbackQueryHandler(cancel_add_product, pattern="^cancel_add_product$"),
        ],
    )
    delivery_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_delivery, pattern="^(admin_delivery|employee_delivery):"),
        ],
        states={
            DELIVERY_CONTENT: [
                MessageHandler(
                    (filters.TEXT & ~filters.COMMAND)
                    | filters.Document.ALL
                    | filters.VIDEO,
                    receive_delivery_content,
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", stop_delivery),
            CallbackQueryHandler(stop_delivery, pattern="^stop_delivery$"),
        ],
    )
    username_category_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                start_add_username_category,
                pattern="^admin_add_username_category$",
            ),
        ],
        states={
            USERNAME_CATEGORY_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_username_category_name,
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_username_admin_flow),
            CallbackQueryHandler(
                cancel_username_admin_flow,
                pattern="^cancel_username_admin_flow$",
            ),
        ],
    )
    username_item_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_add_username, pattern="^(admin_add_username|employee_add_username):"),
        ],
        states={
            USERNAME_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_username_name),
            ],
            USERNAME_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_username_price),
            ],
            USERNAME_DELIVERY: [
                MessageHandler(
                    (filters.TEXT & ~filters.COMMAND)
                    | filters.Document.ALL
                    | filters.VIDEO,
                    receive_username_delivery,
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_username_admin_flow),
            CallbackQueryHandler(
                cancel_username_admin_flow,
                pattern="^cancel_username_admin_flow$",
            ),
        ],
    )
    employee_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_add_employee, pattern="^admin_add_employee$"),
        ],
        states={
            EMPLOYEE_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_employee_id),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_add_employee),
            CallbackQueryHandler(cancel_add_employee, pattern="^cancel_add_employee$"),
        ],
    )
    required_channel_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_set_required_channel, pattern="^admin_set_required_channel$"),
        ],
        states={
            REQUIRED_CHANNEL: [
                CallbackQueryHandler(cancel_required_channel, pattern="^cancel_required_channel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_required_channel),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_required_channel),
            CallbackQueryHandler(cancel_required_channel, pattern="^cancel_required_channel$"),
        ],
    )
    topup_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_topup_amount, pattern="^topup_method:(nowpayments|tap)$"),
            CallbackQueryHandler(start_topup_payment_verification, pattern="^verify_topup:"),
            CallbackQueryHandler(start_latest_topup_payment_verification, pattern="^verify_latest_topup$"),
        ],
        states={
            TOPUP_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_topup_amount),
            ],
            TOPUP_PAYMENT_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_topup_payment_id),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_topup),
            CallbackQueryHandler(cancel_topup, pattern="^cancel_topup$"),
        ],
    )
    support_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_support_ticket, pattern="^support_new:"),
            CallbackQueryHandler(start_add_support_message, pattern="^support_add:"),
        ],
        states={
            SUPPORT_MESSAGE: [
                CallbackQueryHandler(finish_support_ticket, pattern="^support_finish_ticket$"),
                CallbackQueryHandler(cancel_support_ticket, pattern="^support_cancel_ticket$"),
                MessageHandler(
                    (filters.TEXT & ~filters.COMMAND)
                    | filters.PHOTO
                    | filters.Document.ALL
                    | filters.VIDEO,
                    receive_support_message,
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_support_ticket),
            CallbackQueryHandler(cancel_support_ticket, pattern="^support_cancel_ticket$"),
        ],
    )
    staff_ticket_reply_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_staff_ticket_reply, pattern="^staff_ticket_reply:"),
        ],
        states={
            SUPPORT_REPLY_MESSAGE: [
                CallbackQueryHandler(cancel_staff_ticket_reply, pattern="^cancel_staff_ticket_reply$"),
                MessageHandler(
                    (filters.TEXT & ~filters.COMMAND)
                    | filters.PHOTO
                    | filters.Document.ALL
                    | filters.VIDEO,
                    receive_staff_ticket_reply,
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_staff_ticket_reply),
            CallbackQueryHandler(cancel_staff_ticket_reply, pattern="^cancel_staff_ticket_reply$"),
        ],
    )

    broadcast_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_broadcast, pattern="^admin_broadcast$"),
        ],
        states={
            BROADCAST_MESSAGE: [
                MessageHandler(filters.ALL & ~filters.COMMAND, receive_broadcast_message),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_broadcast),
            CallbackQueryHandler(cancel_broadcast, pattern="^cancel_broadcast$"),
        ],
    )

    payment_settings_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_edit_payment_setting, pattern="^edit_payment_setting:"),
        ],
        states={
            PAYMENT_SETTING_INPUT: [
                CallbackQueryHandler(cancel_edit_payment_setting, pattern="^cancel_edit_payment_setting$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_payment_setting_input),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_edit_payment_setting),
            CallbackQueryHandler(cancel_edit_payment_setting, pattern="^cancel_edit_payment_setting$"),
        ],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(broadcast_handler)
    app.add_handler(payment_settings_handler)
    app.add_handler(add_product_handler)
    app.add_handler(delivery_handler)
    app.add_handler(username_category_handler)
    app.add_handler(username_item_handler)
    app.add_handler(employee_handler)
    app.add_handler(required_channel_handler)
    app.add_handler(topup_handler)
    app.add_handler(support_handler)
    app.add_handler(staff_ticket_reply_handler)
    app.add_handler(CallbackQueryHandler(handle_menu))

    LOGGER.info("TikTok Store")
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except NetworkError as error:
        LOGGER.error(
            "Could not connect to Telegram. Check your internet connection, DNS, "
            "VPN/proxy, or firewall settings. Details: %s",
            error,
        )


if __name__ == "__main__":
    main()
