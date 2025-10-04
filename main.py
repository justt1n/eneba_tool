import asyncio
import logging
from datetime import datetime
from time import sleep

from clients.google_sheets_client import GoogleSheetsClient
from clients.impl.eneba_client import EnebaClient
from logic.processor import Processor
from services.eneba_service import EnebaService
from services.sheet_service import SheetService
from utils.config import settings


async def run_automation():
    try:
        g_client = GoogleSheetsClient(settings.GOOGLE_KEY_PATH)
        sheet_service = SheetService(client=g_client)
        payloads_to_process = sheet_service.get_payloads_to_process()
        eneba_client = EnebaClient()
        processor = Processor(eneba_service=EnebaService(eneba_client=eneba_client))

        if not payloads_to_process:
            logging.info("No payloads to process.")
            return

        for payload in payloads_to_process:
            try:
                hydrated_payload = sheet_service.fetch_data_for_payload(payload)
                result = processor.process_single_payload(hydrated_payload)
                if result.status == 1:
                    #TODO: Update price on Eneba
                    #check if quota > 0 then update price
                    _quota_remain, _quota_count = processor.eneba_service.check_next_free_in_minutes(payload.product_id)
                    if _quota_remain is not None and _quota_remain == 0:
                        processor.eneba_service.update_product_price(offer_id=payload.offer_id, new_price=result.final_price.price)
                        logging.info(
                            f"Successfully processed payload for {payload.product_name}. Final price: {result.final_price.price:.3f}"
                            f"\n Quote remain: {_quota_count} times")
                        log_data = {
                            'note': f"Quote remain: {_quota_count} times\n" + result.log_message,
                            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                    else:
                        logging.warning(f"Insufficient quota to update price for {payload.product_name}. Next free "
                                        f"in: {_quota_remain}")
                        log_data = {
                            'note': f"Quota = 0. Next free in: {_quota_remain}"
                                    f"\n{result.log_message}",
                            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                else:
                    logging.warning(f"Payload {payload.product_name} did not meet conditions for processing.")
                    log_data = {
                        'note': result.log_message,
                        'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }

                if log_data:
                    sheet_service.update_log_for_payload(payload, log_data)

                if payload.relax and int(payload.relax) > 0:
                    _sleep = int(payload.relax)
                else:
                    _sleep = 5
                logging.info(f"Processed row {payload.row_index}, sleeping for {_sleep}s.")
                sleep(_sleep)

            except Exception as e:
                logging.error(f"Error in flow for row {payload.row_index}: {e}")
                sheet_service.update_log_for_payload(payload, {'note': f"Error: {e}"})

    except Exception as e:
        logging.critical(f"Đã xảy ra lỗi nghiêm trọng, chương trình dừng lại: {e}", exc_info=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.ERROR)

    while True:
        asyncio.run(run_automation())
        logging.info(f"Completed processing all payloads. Next round in {settings.SLEEP_TIME} seconds.")
        sleep(settings.SLEEP_TIME)
