import asyncio
import logging
from datetime import datetime

import httpx

from clients.google_sheets_client import GoogleSheetsClient
from clients.impl.eneba_client import EnebaClient
from logic.processor import Processor  # File processor.py của bạn (đã async)
from models.sheet_models import Payload  # Cần import Payload
from services.eneba_service import EnebaService
from services.sheet_service import SheetService
from utils.config import settings


# Bỏ 'from time import sleep'


# --- TÁCH LOGIC RA HÀM RIÊNG ---
async def process_payload_wrapper(
        payload: Payload,
        sheet_service: SheetService,
        processor: Processor,
        worker_semaphore: asyncio.Semaphore,  # Đổi tên cho rõ
        google_sheets_lock: asyncio.Semaphore  # Thêm khóa cho Google Sheets
):
    """
    Hàm này xử lý MỘT payload và giải phóng semaphore khi hoàn thành.
    """
    try:
        logging.info(f"Start processing {payload.row_index}...")

        # --- BẢO VỆ GOOGLE SHEETS ---
        async with google_sheets_lock:
            logging.debug(f"Row {payload.row_index} acquiring Google Sheets lock to fetch data.")
            # 1. Lấy dữ liệu (đồng bộ)
            hydrated_payload = await asyncio.to_thread(
                sheet_service.fetch_data_for_payload, payload
            )
            logging.debug(f"Row {payload.row_index} released Google Sheets lock.")
        # --- KẾT THÚC BẢO VỆ ---

        # 2. Kiểm tra quota (bất đồng bộ - CÓ THỂ CHẠY SONG SONG)
        hydrated_payload, _quota_remain, _quota_count = await processor.eneba_service.check_next_free_in_minutes(
            hydrated_payload)

        # 3. Xử lý logic (bất đồng bộ - CÓ THỂ CHẠY SONG SONG)
        result = await processor.process_single_payload(hydrated_payload)

        log_data = None

        if result.status == 1:
            if _quota_remain is not None and _quota_count > 0:
                # 4. Cập nhật giá (bất đồng bộ - CÓ THỂ CHẠY SONG SONG)
                await processor.eneba_service.update_product_price(
                    offer_id=payload.offer_id, new_price=result.final_price.price
                )

                logging.info(
                    f"Xử lý thành công hàng {payload.row_index} ({payload.product_name}). "
                    f"Giá mới: {result.final_price.price:.3f}. Còn {_quota_count} lượt.")
                log_data = {
                    'note': f"Quote remain: {_quota_count} times\n" + result.log_message,
                    'last_update': datetime.now().strftime('%Y-m-%d %H:%M:%S')
                }
            else:
                logging.warning(f"Không đủ quota cho hàng {payload.row_index}. Chờ {_quota_remain} phút.")
                log_data = {
                    'note': f"Quota = 0. Next free in: {_quota_remain}\n{result.log_message}",
                    'last_update': datetime.now().strftime('%Y-m-%d %H:%M:%S')
                }
        elif result.status == 2:
            logging.info(f"Giá hiện tại thấp hơn, không cập nhật hàng {payload.row_index}. Còn {_quota_count} lượt.")
            log_data = {
                'note': f"Quote remain: {_quota_count} times\n" + result.log_message,
                'last_update': datetime.now().strftime('%Y-m-%d %H:%M:%S')
            }
        else:
            logging.warning(f"Hàng {payload.row_index} không đủ điều kiện xử lý. Log: {result.log_message}")
            log_data = {
                'note': result.log_message,
                'last_update': datetime.now().strftime('%Y-m-%d %H:%M:%S')
            }

        if log_data:
            # --- BẢO VỆ GOOGLE SHEETS ---
            async with google_sheets_lock:
                logging.debug(f"Row {payload.row_index} acquiring Google Sheets lock to update log.")
                # 5. Cập nhật log (đồng bộ)
                await asyncio.to_thread(
                    sheet_service.update_log_for_payload, payload, log_data
                )
                logging.debug(f"Row {payload.row_index} released Google Sheets lock.")
            # --- KẾT THÚC BẢO VỆ ---

        # 6. Nghỉ ngơi (nếu có config)
        if payload.relax and int(payload.relax) > 0:
            _sleep = int(payload.relax)
            logging.info(f"Done row {payload.row_index} this worker sleep for {_sleep}s.")
            await asyncio.sleep(_sleep)

        logging.info(f"Done row {payload.row_index}.")

    except Exception as e:
        logging.error(f"Lỗi nghiêm trọng khi xử lý hàng {payload.row_index}: {e}", exc_info=True)
        try:
            # --- BẢO VỆ GOOGLE SHEETS (kể cả khi log lỗi) ---
            async with google_sheets_lock:
                logging.debug(f"Row {payload.row_index} acquiring Google Sheets lock to log error.")
                # Ghi lại lỗi lên sheet (đồng bộ)
                await asyncio.to_thread(
                    sheet_service.update_log_for_payload, payload, {'note': f"Error: {e}"}
                )
                logging.debug(f"Row {payload.row_index} released Google Sheets lock.")
            # --- KẾT THÚC BẢO VỆ ---
        except Exception as log_e:
            logging.error(f"Không thể ghi log lỗi cho hàng {payload.row_index}: {log_e}")

    finally:
        # Quan trọng: Luôn giải phóng semaphore để task tiếp theo được vào
        worker_semaphore.release()


# --- HÀM CHÍNH ĐÃ SỬA ---
async def run_automation(
        sheet_service: SheetService,
        processor: Processor,
        google_sheets_lock: asyncio.Semaphore  # Thêm tham số
):
    CONCURRENT_TASKS = settings.WORKERS

    worker_semaphore = asyncio.Semaphore(CONCURRENT_TASKS)  # Đây là semaphore cho worker
    tasks = []

    try:
        logging.info("Getting payloads from Google Sheets...")

        # Chỉ có 1 tác vụ đọc sheet, nên không cần khóa ở đây
        payloads_to_process = await asyncio.to_thread(
            sheet_service.get_payloads_to_process
        )

        if not payloads_to_process:
            logging.info("No payloads to process.")
            return

        logging.info(
            f"Found {len(payloads_to_process)} payloads. Start to process (max {CONCURRENT_TASKS} row)...")

        for payload in payloads_to_process:
            await worker_semaphore.acquire()

            task = asyncio.create_task(
                process_payload_wrapper(
                    payload,
                    sheet_service,
                    processor,
                    worker_semaphore,  # Semaphore cho worker
                    google_sheets_lock  # Khóa cho Google Sheets
                )
            )
            tasks.append(task)

        await asyncio.gather(*tasks)
        logging.info("Complete row.")

    except Exception as e:
        logging.critical(f"Error in processing row: {e}", exc_info=True)


async def main():
    """
    Hàm async chính: Khởi tạo các client và chạy vòng lặp vô hạn.
    """
    connection_limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)

    # Thêm một khóa (Semaphore(1))
    google_sheets_lock = asyncio.Semaphore(1)

    async with httpx.AsyncClient(limits=connection_limits, timeout=30.0) as shared_http_client:
        logging.info("Shared HTTP client pool init.")

        g_client = GoogleSheetsClient(settings.GOOGLE_KEY_PATH)
        sheet_service = SheetService(client=g_client)

        eneba_client = EnebaClient(http_client=shared_http_client)
        eneba_service = EnebaService(eneba_client=eneba_client)

        processor = Processor(eneba_service=eneba_service)

        while True:
            try:
                logging.info("===== New round =====")
                # Truyền khóa vào
                await run_automation(sheet_service, processor, google_sheets_lock)

                logging.info(f"Complete the round, next round in {settings.SLEEP_TIME} seconds.")
                await asyncio.sleep(settings.SLEEP_TIME)

            except Exception as e:
                logging.critical(f"Error in main, retry in 30s: {e}", exc_info=True)
                await asyncio.sleep(30)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # Thêm debug để thấy lock
    # logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Stop by user.")
