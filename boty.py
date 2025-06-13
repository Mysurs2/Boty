from keep_alive import keep_alive
keep_alive()

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, ConversationHandler, filters
)
from PIL import Image, ImageDraw, ImageEnhance, UnidentifiedImageError
from io import BytesIO
import requests
import os
import logging

# --- إعدادات التسجيل ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- معرف المالك والتوكن ---
OWNER_ID = 5096360287
TELEGRAM_TOKEN = "8178257536:AAEhQjCUDC_vv7xmR71FBpVgEK2SunPLbeQ" # Your provided token

# --- ملفات مفاتيح API ---
PICSART_KEY_FILE = "picsart_api_key.txt"
REMOVEBG_KEY_FILE = "removebg_api_key.txt"

for key_file in [PICSART_KEY_FILE, REMOVEBG_KEY_FILE]:
    if not os.path.exists(key_file):
        with open(key_file, "w") as f:
            f.write("")
        logger.info(f"تم إنشاء ملف المفتاح الفارغ: {key_file}")

# --- إعدادات القالب ---
dpi = 300
cm_to_px = lambda cm: int((cm / 2.54) * dpi)
paper_w_cm, paper_h_cm = 10, 15
img_w_cm, img_h_cm = 3, 4
canvas_width = cm_to_px(paper_w_cm)
canvas_height = cm_to_px(paper_h_cm)
img_w = cm_to_px(img_w_cm)
img_h = cm_to_px(img_h_cm)
cols, rows = 3, 3
spacing = 6
border_thickness = 4
border_color = (200, 200, 200)

# --- حالات المحادثة لإدخال المفاتيح ---
(ENTER_PICSART_KEY, ENTER_REMOVEBG_KEY) = range(2)

# --- دوال مساعدة للمفاتيح ---
def load_key(file_path: str) -> str:
    try:
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return f.read().strip()
    except Exception as e:
        logger.error(f"خطأ في تحميل المفتاح من {file_path}: {e}")
    return ""

def save_key(file_path: str, key: str):
    try:
        with open(file_path, "w") as f:
            f.write(key)
        logger.info(f"تم حفظ المفتاح في {file_path}")
    except Exception as e:
        logger.error(f"خطأ في حفظ المفتاح في {file_path}: {e}")

# --- دوال معالجة الصور ---
def auto_crop_to_3x4(image: Image.Image) -> Image.Image:
    w, h = image.size
    target_ratio = 3 / 4.0
    current_ratio = w / float(h)
    if abs(current_ratio - target_ratio) < 0.01:
        return image
    if current_ratio > target_ratio:
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        right = left + new_w
        return image.crop((left, 0, right, h))
    else:
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        bottom = top + new_h
        return image.crop((0, top, w, bottom))

# --- تعريف القوائم ---
MAIN_MENU = [
    ["إزالة الخلفية"], ["زيادة التباين"], ["تحسين الجودة"], ["توزيع داخل قالب"]
]
ADMIN_MENU = [["مفاتيح إزالة الخلفية"], ["مفاتيح تحسين الصور"], ["رجوع"]]
REMOVEBG_MENU = [["تغيير مفتاح إزالة الخلفية"], ["حذف مفتاح إزالة الخلفية"], ["عرض مفتاح إزالة الخلفية"], ["رجوع"]]
PICSART_MENU = [["تغيير مفتاح تحسين الصور"], ["حذف مفتاح تحسين الصور"], ["عرض مفتاح تحسين الصور"], ["رجوع"]]

# --- معالجات الأوامر والرسائل ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"المستخدم {user.id} بدأ المحادثة.")
    is_owner = user.id == OWNER_ID
    keyboard = MAIN_MENU + ([["إدارة المفاتيح"]] if is_owner else [])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("مرحباً! أنا بوت لمساعدتك في معالجة الصور. اختر إحدى الوظائف من القائمة:", reply_markup=reply_markup)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    logger.info(f"المستخدم {user_id} أرسل النص: {text}")
    is_owner = user_id == OWNER_ID
    context.user_data.pop('mode', None)

    if text == "إدارة المفاتيح" and is_owner:
        await update.message.reply_text("إدارة المفاتيح:", reply_markup=ReplyKeyboardMarkup(ADMIN_MENU, resize_keyboard=True))
    elif text == "مفاتيح إزالة الخلفية" and is_owner:
        await update.message.reply_text("إعدادات مفتاح Remove.bg:", reply_markup=ReplyKeyboardMarkup(REMOVEBG_MENU, resize_keyboard=True))
    elif text == "مفاتيح تحسين الصور" and is_owner:
        await update.message.reply_text("إعدادات مفتاح Picsart:", reply_markup=ReplyKeyboardMarkup(PICSART_MENU, resize_keyboard=True))
    elif text == "تغيير مفتاح إزالة الخلفية" and is_owner:
        context.user_data["next_action"] = "set_removebg_key"
        await update.message.reply_text("من فضلك، أرسل المفتاح الجديد لـ Remove.bg:")
        return ENTER_REMOVEBG_KEY
    elif text == "تغيير مفتاح تحسين الصور" and is_owner:
        context.user_data["next_action"] = "set_picsart_key"
        await update.message.reply_text("من فضلك، أرسل المفتاح الجديد لـ Picsart:")
        return ENTER_PICSART_KEY
    elif text == "حذف مفتاح إزالة الخلفية" and is_owner:
        save_key(REMOVEBG_KEY_FILE, "")
        await update.message.reply_text("تم حذف مفتاح Remove.bg بنجاح.")
    elif text == "حذف مفتاح تحسين الصور" and is_owner:
        save_key(PICSART_KEY_FILE, "")
        await update.message.reply_text("تم حذف مفتاح Picsart بنجاح.")
    elif text == "عرض مفتاح إزالة الخلفية" and is_owner:
        key = load_key(REMOVEBG_KEY_FILE)
        await update.message.reply_text(f"مفتاح Remove\\.bg الحالي:\n`{key or 'غير معين'}`", parse_mode="MarkdownV2")
    elif text == "عرض مفتاح تحسين الصور" and is_owner:
        key = load_key(PICSART_KEY_FILE)
        await update.message.reply_text(f"مفتاح Picsart الحالي:\n`{key or 'غير معين'}`", parse_mode="MarkdownV2")
    elif text == "تحسين الجودة":
        key = load_key(PICSART_KEY_FILE)
        if not key:
            await update.message.reply_text("عذراً، لم يتم تعيين مفتاح Picsart لتحسين جودة الصور بعد. يرجى التواصل مع مالك البوت.")
            if is_owner:
                 await update.message.reply_text("يمكنك تعيين المفتاح من قائمة 'إدارة المفاتيح'.")
            return
        context.user_data['mode'] = "enhance"
        await update.message.reply_text("أرسل صورة لتحسين جودتها باستخدام Picsart.")
    elif text == "إزالة الخلفية":
        key = load_key(REMOVEBG_KEY_FILE)
        if not key:
            await update.message.reply_text("عذراً، لم يتم تعيين مفتاح Remove.bg لإزالة الخلفية بعد. يرجى التواصل مع مالك البوت.")
            if is_owner:
                 await update.message.reply_text("يمكنك تعيين المفتاح من قائمة 'إدارة المفاتيح'.")
            return
        context.user_data['mode'] = "removebg"
        await update.message.reply_text("أرسل صورة وسأقوم بإزالة خلفيتها باستخدام Remove.bg.")
    elif text == "زيادة التباين":
        context.user_data['mode'] = "contrast"
        await update.message.reply_text("أرسل صورة لزيادة تباينها ووضوحها.")
    elif text == "توزيع داخل قالب":
        context.user_data['mode'] = "template"
        await update.message.reply_text("أرسل صورة شخصية (يفضل بنسبة 3:4) وسأقوم بتوزيعها 9 مرات في قالب بحجم 10x15 سم.")
    elif text == "رجوع":
        await start(update, context)
    else:
        keyboard = MAIN_MENU + ([["إدارة المفاتيح"]] if is_owner else [])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        await update.message.reply_text("لم أفهم طلبك. يرجى استخدام الأزرار أو إرسال /start للبدء.", reply_markup=reply_markup)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get('mode')
    if not mode:
        await update.message.reply_text("يرجى اختيار وظيفة أولاً من القائمة.")
        return

    photo_size_obj = update.message.photo[-1]
    file_id = photo_size_obj.file_id

    telegram_file_obj = await context.bot.get_file(file_id)

    # Variables for image data, loaded conditionally
    img_bytes_io_for_upload = None # For modes like removebg that upload bytes
    pil_image_obj = None           # For modes like contrast, template that use PIL

    if mode != "enhance": # For modes other than enhance (which will use URL directly)
        try:
            img_data_bytearray = await telegram_file_obj.download_as_bytearray()
            # For removebg and potentially others that might upload raw bytes
            img_bytes_io_for_upload = BytesIO(img_data_bytearray)

            # For modes that require PIL processing
            if mode in ["contrast", "template"]:
                 # Create a new BytesIO for PIL to avoid cursor issues if img_bytes_io_for_upload is also used
                pil_image_obj = Image.open(BytesIO(img_data_bytearray))
        except UnidentifiedImageError:
            logger.warning(f"المستخدم {update.effective_user.id} أرسل ملفًا غير صالح كصورة.")
            await update.message.reply_text("الملف المرسل ليس صورة صالحة. يرجى إرسال صورة بتنسيق شائع (مثل JPG أو PNG).")
            return
        except Exception as e:
            logger.error(f"خطأ أثناء تحميل/معالجة الصورة الأولية: {e}")
            await update.message.reply_text("حدث خطأ أثناء تحميل الصورة. حاول مرة أخرى.")
            return

    processing_msg = await update.message.reply_text("⏳ جاري معالجة الصورة...")

    try:
        if mode == "removebg":
            api_key = load_key(REMOVEBG_KEY_FILE)
            if not api_key:
                await processing_msg.edit_text("مفتاح Remove.bg غير معين. لا يمكن إزالة الخلفية.")
                return
            if not img_bytes_io_for_upload:
                logger.error("img_bytes_io_for_upload is None for removebg mode.")
                await processing_msg.edit_text("خطأ داخلي: لم يتم تحميل بيانات الصورة بشكل صحيح.")
                return

            img_bytes_io_for_upload.seek(0)
            response = requests.post(
                "https://api.remove.bg/v1.0/removebg",
                files={"image_file": ("image.png", img_bytes_io_for_upload, "image/png")},
                data={"size": "auto"},
                headers={"X-Api-Key": api_key},
                timeout=30
            )
            response.raise_for_status()
            output_image = BytesIO(response.content)
            output_image.name = "background_removed.png"
            await update.message.reply_photo(photo=output_image, caption="✅ تمت إزالة الخلفية بنجاح!")

        elif mode == "enhance":
            api_key = load_key(PICSART_KEY_FILE)
            if not api_key:
                await processing_msg.edit_text("مفتاح Picsart غير معين. لا يمكن تحسين الجودة.")
                return

            original_image_telegram_url = telegram_file_obj.file_path # URL of original image on Telegram servers

            await processing_msg.edit_text("⬆️ جاري تحسين الجودة باستخدام Picsart (عبر الرابط)...")

            payload_data = {'upscale_factor': 2}
            # Send image_url as a form field via the 'files' parameter, as per user's snippet structure
            files_payload_for_api = {'image_url': (None, original_image_telegram_url)}
            headers = {'x-picsart-api-key': api_key}

            response = requests.post(
                "https://api.picsart.io/tools/1.0/upscale",  # Changed endpoint
                headers=headers,
                data=payload_data,      # For parameters like upscale_factor
                files=files_payload_for_api, # For image_url
                timeout=60
            )
            response.raise_for_status()

            result = response.json()
            if result.get("status") == "success" and result.get("data", {}).get("url"):
                enhanced_image_url_from_picsart = result["data"]["url"]
                # Let Telegram download and send the image directly from the Picsart URL
                await update.message.reply_photo(
                    photo=enhanced_image_url_from_picsart,
                    caption="✅ تم تحسين جودة الصورة بنجاح!"
                )
            else:
                picsart_error_message = "فشل في معالجة الصورة من خلال Picsart."
                if isinstance(result.get('error'), dict):
                    picsart_error_message = result['error'].get('message', picsart_error_message)
                elif 'detail' in result:
                    picsart_error_message = result.get('detail')
                elif 'message' in result:
                    picsart_error_message = result.get('message')

                if result.get("status") != "success" and picsart_error_message == "فشل في معالجة الصورة من خلال Picsart.":
                    picsart_error_message = f"فشل الطلب. الاستجابة من Picsart: {str(result)[:200]}"

                logger.error(f"Picsart API (/upscale) لم يُرجع رابطًا صالحًا أو أرجع خطأ: {result}")
                await update.message.reply_text(f"❌ لم يتم العثور على رابط الصورة المحسنة أو حدث خطأ.\nتفاصيل الخطأ من Picsart: {picsart_error_message}")

        elif mode == "contrast":
            if not pil_image_obj:
                logger.error("pil_image_obj is None for contrast mode.")
                await processing_msg.edit_text("خطأ داخلي: لم يتم تحميل بيانات الصورة بشكل صحيح لمعالجة التباين.")
                return

            img_to_process = pil_image_obj
            if img_to_process.mode == 'RGBA':
                img_to_process = img_to_process.convert('RGB')

            img_resized = img_to_process.resize((img_to_process.width * 2, img_to_process.height * 2), Image.LANCZOS)
            enhancer_sharpness = ImageEnhance.Sharpness(img_resized)
            img_sharpened = enhancer_sharpness.enhance(1.5)
            enhancer_contrast = ImageEnhance.Contrast(img_sharpened)
            img_contrasted = enhancer_contrast.enhance(1.2)

            output_image = BytesIO()
            img_contrasted.save(output_image, format="JPEG", quality=90)
            output_image.seek(0)
            output_image.name = "contrast_enhanced.jpg"
            await update.message.reply_photo(photo=output_image, caption="✅ تم زيادة التباين والوضوح بنجاح!")

        elif mode == "template":
            if not pil_image_obj:
                logger.error("pil_image_obj is None for template mode.")
                await processing_msg.edit_text("خطأ داخلي: لم يتم تحميل بيانات الصورة بشكل صحيح لإنشاء القالب.")
                return

            img_to_process = pil_image_obj
            img_cropped = auto_crop_to_3x4(img_to_process.convert("RGBA"))
            img_resized_for_template = img_cropped.resize((img_w, img_h), Image.LANCZOS)
            canvas = Image.new("RGB", (canvas_width, canvas_height), (255, 255, 255))
            draw = ImageDraw.Draw(canvas)
            for r_idx in range(rows):
                for c_idx in range(cols):
                    x = c_idx * (img_w + spacing) + spacing // 2
                    y = r_idx * (img_h + spacing) + spacing // 2
                    if x + img_w <= canvas_width and y + img_h <= canvas_height:
                        canvas.paste(img_resized_for_template, (x, y), img_resized_for_template if img_resized_for_template.mode == 'RGBA' else None)
                        draw.rectangle(
                            (x - border_thickness // 2, y - border_thickness // 2,
                             x + img_w + border_thickness // 2, y + img_h + border_thickness // 2),
                            outline=border_color, width=border_thickness)
            draw.rectangle((0,0, canvas_width-1, canvas_height-1), outline=border_color, width=border_thickness // 2)
            output_image = BytesIO()
            canvas.save(output_image, format="JPEG", quality=95, dpi=(dpi,dpi))
            output_image.seek(0)
            output_image.name = "photo_template.jpg"
            await update.message.reply_document(
                document=output_image,
                filename="photo_template_10x15cm_300dpi.jpg",
                caption=f"✅ تم إنشاء القالب بنجاح (9 صور 3x4 سم على ورق 10x15 سم بدقة {dpi} DPI).")

    except requests.exceptions.RequestException as e:
        status_code_text = ""
        response_text_info = ""
        error_message_from_api = ""
        if hasattr(e, 'response') and e.response is not None:
            status_code_text = f" (كود الخطأ: {e.response.status_code})"
            try:
                response_text_info = f" - {e.response.text}"
                try:
                    error_data = e.response.json()
                    if isinstance(error_data.get('error'), dict):
                         error_message_from_api = error_data['error'].get('message', '')
                    elif 'detail' in error_data: error_message_from_api = error_data.get('detail', '')
                    elif 'message' in error_data: error_message_from_api = error_data.get('message', '')
                    if not error_message_from_api: error_message_from_api = e.response.text
                except ValueError: error_message_from_api = e.response.text
            except Exception:
                response_text_info = " - (لا يمكن قراءة نص الاستجابة)"
                error_message_from_api = e.response.text if hasattr(e.response, 'text') else "خطأ غير معروف من الخادم."

        # Specific check for ProxyError which might not have e.response
        if isinstance(e, requests.exceptions.ProxyError):
            error_message = f"حدث خطأ في الاتصال بالشبكة (ProxyError) عند محاولة الوصول إلى خدمة {mode}."
            logger.error(f"ProxyError في API ({mode}): {e}")
        else:
            logger.error(f"خطأ في API ({mode}): {e}{status_code_text}{response_text_info}")
            error_message = f"حدث خطأ أثناء الاتصال بخدمة {mode}."

        if hasattr(e, 'response') and e.response is not None: # Add details if response object exists
            if mode == "removebg":
                if e.response.status_code == 402: error_message = "نفذ رصيد حساب Remove.bg أو أن المفتاح غير صالح."
                elif e.response.status_code == 403: error_message = "مفتاح Remove.bg غير صالح."
                if error_message_from_api and not (e.response.status_code == 402 or e.response.status_code == 403) : error_message += f"\nتفاصيل: {error_message_from_api}"
            elif mode == "enhance":
                if e.response.status_code == 401: error_message = "مفتاح Picsart غير صالح أو انتهت صلاحيته."
                elif e.response.status_code == 400: error_message = "فشل طلب تحسين الصورة (Bad Request)."
                if error_message_from_api and not (e.response.status_code == 401 or e.response.status_code == 400): error_message += f"\nتفاصيل من Picsart: {error_message_from_api}"

        await update.message.reply_text(f"❌ {error_message}{status_code_text}")
    except Exception as e:
        logger.exception(f"خطأ غير متوقع في معالجة الصورة ({mode}): {e}")
        await update.message.reply_text(f"❌ حدث خطأ غير متوقع أثناء معالجة الصورة في وضع '{mode}'.")
    finally:
        await processing_msg.delete()
        context.user_data.pop('mode', None)

async def set_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_key = update.message.text.strip()
    action = context.user_data.pop("next_action", None)
    if not new_key:
        await update.message.reply_text("لم يتم إرسال مفتاح. لم يتم إجراء أي تغيير.")
        await start(update, context)
        return ConversationHandler.END
    if action == "set_picsart_key":
        save_key(PICSART_KEY_FILE, new_key)
        await update.message.reply_text("✅ تم حفظ مفتاح Picsart بنجاح!")
        logger.info(f"مالك البوت {update.effective_user.id} قام بتحديث مفتاح Picsart.")
    elif action == "set_removebg_key":
        save_key(REMOVEBG_KEY_FILE, new_key)
        await update.message.reply_text("✅ تم حفظ مفتاح Remove.bg بنجاح!")
        logger.info(f"مالك البوت {update.effective_user.id} قام بتحديث مفتاح Remove.bg.")
    else:
        await update.message.reply_text("حدث خطأ غير متوقع أثناء محاولة تعيين المفتاح.")
        logger.warning("تم استدعاء set_key بدون next_action صالح أو بقيمة غير متوقعة.")
    await start(update, context)
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await start(update, context)
    logger.info(f"المستخدم {update.effective_user.id} ألغى المحادثة.")
    return ConversationHandler.END

def main():
    logger.info("بدء تشغيل البوت...")
    if not TELEGRAM_TOKEN or len(TELEGRAM_TOKEN.split(':')) != 2:
        logger.error("!!! توكن البوت غير معين أو بتنسيق خاطئ. !!!")
        print("!!! توكن البوت غير معين أو بتنسيق خاطئ. !!!")
        return
    if not isinstance(OWNER_ID, int) or OWNER_ID == 0:
        logger.error("!!! معرف المالك OWNER_ID غير معين أو غير صحيح. !!!")
        print("!!! معرف المالك OWNER_ID غير معين أو غير صحيح. !!!")
        return

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & (filters.Regex("تغيير مفتاح إزالة الخلفية") | filters.Regex("تغيير مفتاح تحسين الصور")) & filters.User(user_id=OWNER_ID), handle_text)],
        states={
            ENTER_PICSART_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(user_id=OWNER_ID), set_key)],
            ENTER_REMOVEBG_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(user_id=OWNER_ID), set_key)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation), MessageHandler(filters.TEXT & filters.Regex("رجوع") & filters.User(user_id=OWNER_ID), cancel_conversation)],
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    logger.info("تم إعداد المعالجات. البوت جاهز لاستقبال التحديثات.")
    try:
        application.run_polling()
    except Exception as e:
        logger.critical(f"فشل تشغيل البوت بسبب خطأ فادح: {e}", exc_info=True)
    finally:
        logger.info("تم إيقاف البوت.")

if __name__ == "__main__":
    main()
