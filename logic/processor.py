import logging
import random
from datetime import datetime
from typing import List

from models.eneba_models import CompetitionEdge
from models.logic_models import PayloadResult, CompareTarget, AnalysisResult
from models.sheet_models import Payload
from services.eneba_service import EnebaService  # Đây là EnebaService phiên bản async
from utils.utils import round_up_to_n_decimals


class Processor:
    def __init__(self, eneba_service: EnebaService):
        self.eneba_service = eneba_service

    # Hàm này là logic thuần túy, không cần async
    def _calc_final_price_old(self, payload: Payload, price: float) -> float:
        if price is None:
            price = round_up_to_n_decimals(payload.fetched_max_price, payload.price_rounding)
            logging.info(f"No product match, using fetched max price: {price:.3f}")
        if payload.min_price_adjustment is None or payload.max_price_adjustment is None:
            pass
        else:
            min_adj = min(payload.min_price_adjustment, payload.max_price_adjustment)
            max_adj = max(payload.min_price_adjustment, payload.max_price_adjustment)

            d_price = random.uniform(min_adj, max_adj)
            price = price - d_price

        if payload.fetched_min_price is not None:
            price = max(price, payload.fetched_min_price)

        if payload.fetched_max_price is not None:
            price = min(price, payload.fetched_max_price)

        if payload.price_rounding is not None:
            price = round_up_to_n_decimals(price, payload.price_rounding)

        return price

    # Hàm này là logic thuần túy, không cần async
    def _calc_final_price(self, payload: Payload, price: float) -> float:
        if price is None:
            price = round_up_to_n_decimals(payload.fetched_max_price, payload.price_rounding)
            logging.info(f"No product match, using fetched max price: {price:.3f}")

        # --- SỬA ĐỔI ---
        # Kiểm tra xem có cấu hình điều chỉnh giá hay không
        if payload.min_price_adjustment is not None and payload.max_price_adjustment is not None:

            # Kiểm tra xem giá đầu vào có phải là giá max hay không
            is_max_price = False
            if payload.fetched_max_price is not None and price == payload.fetched_max_price:
                is_max_price = True

            # Kiểm tra xem giá đầu vào có phải là giá min hay không
            is_min_price = False
            if payload.fetched_min_price is not None and price == payload.fetched_min_price:
                is_min_price = True

            # Chỉ trừ d_price nếu giá hiện tại KHÔNG PHẢI là giá max VÀ KHÔNG PHẢI là giá min
            if not is_max_price and not is_min_price:
                min_adj = min(payload.min_price_adjustment, payload.max_price_adjustment)
                max_adj = max(payload.min_price_adjustment, payload.max_price_adjustment)

                d_price = random.uniform(min_adj, max_adj)
                price = price - d_price
                logging.info(f"Applied random adjustment of -{d_price:.3f}. New price: {price:.3f}")
            else:
                # Ghi log rằng chúng ta đã bỏ qua việc điều chỉnh ngẫu nhiên
                logging.info(f"Price ({price:.3f}) matches a boundary (min or max), skipping random adjustment.")

        # --- KẾT THÚC SỬA ĐỔI ---

        # Các bước kẹp giá (clamping) này vẫn RẤT CẦN THIẾT
        # để đảm bảo giá sau khi trừ d_price không bị lọt ra ngoài khoảng min/max
        if payload.fetched_min_price is not None:
            price = max(price, payload.fetched_min_price)

        if payload.fetched_max_price is not None:
            price = min(price, payload.fetched_max_price)

        if payload.price_rounding is not None:
            price = round_up_to_n_decimals(price, payload.price_rounding)

        return price

    # Hàm này là logic thuần túy, không cần async
    def _validate_payload(self, payload: Payload) -> bool:
        if not payload.product_name:
            logging.warning("Payload validation failed: product_name is required.")
            return False
        if payload.price_rounding is not None and payload.price_rounding < 0:
            logging.warning("Payload validation failed: price_rounding cannot be negative.")
            return False
        if payload.min_price_adjustment is not None and payload.max_price_adjustment is not None:
            if payload.min_price_adjustment > payload.max_price_adjustment:
                logging.warning(
                    "Payload validation failed: min_price_adjustment cannot be greater than max_price_adjustment.")
                return False
        if payload.product_id is None:
            logging.warning("Payload validation failed: product_id is required.")
            return False
        if payload.product_compare is None:
            logging.warning("Payload validation failed: product_compare is required.")
            return False
        return True

    # Chuyển sang `async def` vì nó gọi service
    async def process_single_payload(self, payload: Payload) -> PayloadResult:
        if not self._validate_payload(payload):
            return PayloadResult(payload=payload, log_message="Payload validation failed.")
        try:
            if not payload.is_compare_enabled:
                logging.info(f"Skipping comparison for product: {payload.product_name}")
                final_price = round_up_to_n_decimals(payload.fetched_min_price, payload.price_rounding)
                log_str = get_log_string(
                    mode="not_compare",
                    payload=payload,
                    final_price=final_price
                )
                return PayloadResult(
                    status=1,
                    payload=payload,
                    final_price=CompareTarget(name="No Comparison", price=final_price),
                    log_message=log_str
                )

            payload.product_compare = payload.product_compare.replace("https://", "").split("/")[1]

            # Thêm `await`
            product_competition = await self.eneba_service.get_competition_by_slug(payload.product_compare)

            # Thêm `await`
            product_id = await self.eneba_service.get_product_id_by_slug(payload.product_compare)
            payload.prod_uuid = str(product_id)

            # Hàm này là sync (chỉ xử lý chuỗi), không cần await
            payload.offer_id = self.eneba_service.get_offer_id_by_url(payload.product_id)

            if not product_competition:
                logging.warning(f"No competition data found for product: {payload.product_name}")
                return PayloadResult(status=0, payload=payload, log_message="No competition data found.")

            # Thêm `await`
            analysis_result = await self.eneba_service.analyze_competition(payload, product_competition)

            payload.target_price = analysis_result.competitive_price

            # Hàm này là sync (logic), không cần await
            edited_price = self._calc_final_price(payload, analysis_result.competitive_price)

            if payload.get_min_price_value() is not None and edited_price < payload.get_min_price_value():
                logging.info(
                    f"Final price ({edited_price:.3f}) is below min_price ({payload.get_min_price_value():.3f}), not updating.")
                log_str = get_log_string(
                    mode="below_min",
                    payload=payload,
                    final_price=edited_price,
                    analysis_result=analysis_result,
                    filtered_products=product_competition
                )
                return PayloadResult(
                    status=0,
                    payload=payload,
                    final_price=None,
                    log_message=log_str
                )
            elif payload.get_min_price_value() is None:
                logging.info("No min_price set, not updating.")
                log_str = get_log_string(
                    mode="no_min_price",
                    payload=payload,
                    final_price=edited_price,
                    analysis_result=analysis_result,
                    filtered_products=product_competition
                )
                return PayloadResult(
                    status=0,
                    payload=payload,
                    final_price=None,
                    log_message=log_str
                )
            elif not payload.is_follow_price and payload.current_price <= payload.target_price and analysis_result.competitor_name != "Not found":
                logging.info("Not follow the price, not updating.")
                log_str = get_log_string(
                    mode="not_follow",
                    payload=payload,
                    final_price=edited_price,
                    analysis_result=analysis_result,
                    filtered_products=product_competition
                )
                return PayloadResult(
                    status=2,
                    payload=payload,
                    final_price=None,
                    log_message=log_str
                )
            elif payload.current_price == edited_price:
                logging.info("Current price is equal to edited price.")
                log_str = get_log_string(
                    mode="equal",
                    payload=payload,
                    final_price=edited_price,
                    analysis_result=analysis_result,
                    filtered_products=product_competition
                )
                return PayloadResult(
                    status=0,
                    payload=payload,
                    final_price=None,
                    log_message=log_str
                )
            log_str = get_log_string(
                mode="compare",
                payload=payload,
                final_price=edited_price,
                analysis_result=analysis_result,
                filtered_products=product_competition
            )
            return PayloadResult(
                status=1,
                payload=payload,
                competition=product_competition,
                final_price=CompareTarget(name=analysis_result.competitor_name, price=edited_price),
                log_message=log_str
            )
        except Exception as e:
            logging.error(f"Error processing payload {payload.product_name}: {e}")
            return PayloadResult(
                status=1,
                payload=payload,
                log_message=f"Error processing payload: {str(e)}",
                final_price=None
            )

    # Chuyển sang `async def` vì nó gọi `process_single_payload`
    async def do_payload(self, payload: Payload):
        # Thêm `await`
        payload_result = await self.process_single_payload(payload)

        if payload_result.status == 1:
            # TODO: Implement the logic to update the product price in the database or API
            # Nếu logic này cũng là I/O (ví dụ: gọi service.update_price), nó cũng cần `await`
            logging.info(
                f"Successfully processed payload for {payload.product_name}. Final price: {payload_result.final_price.price:.3f}")
            log_data = {
                'note': payload_result.log_message,
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        else:
            logging.error(f"Failed to process payload for {payload.product_name}. Error: {payload_result.log_message}")


# Hàm này là logic thuần túy, không cần async
def _analysis_log_string(
        payload: Payload,
        analysis_result: AnalysisResult = None,
        filtered_products: List[CompetitionEdge] = None
) -> str:
    log_parts = []
    if analysis_result.competitor_name == "Not found":
        competitor_name = "Max price"
    else:
        competitor_name = analysis_result.competitor_name
    log_parts.append(f"- GiaHienTai: {payload.current_price}\n")
    competitor_price = analysis_result.competitive_price
    if competitor_price is None or competitor_price == -1:
        competitor_price = payload.fetched_max_price
    if competitor_name and competitor_price is not None:
        log_parts.append(f" - GiaSosanh: {competitor_name} = {competitor_price:.6f}\n")

    price_min_str = f"{payload.fetched_min_price:.6f}" if payload.fetched_min_price is not None else "None"
    price_max_str = f"{payload.fetched_max_price:.6f}" if payload.fetched_max_price is not None else "None"
    log_parts.append(f"PriceMin = {price_min_str}, PriceMax = {price_max_str}\n")

    sellers_below = analysis_result.sellers_below_min
    if sellers_below:
        sellers_info = "; ".join([
            f"{s.node.merchant_name} = {s.node.price.price_no_commission} ({s.node.price.old_price_with_commission:.6f})\n"
            for s in sellers_below[:6] if
            s.node.merchant_name not in payload.fetched_black_list])
        log_parts.append(f"Seller giá nhỏ hơn min_price):\n {sellers_info}")

    log_parts.append("Top 4 sản phẩm:\n")
    sorted_product = sorted(filtered_products, key=lambda item: item.node.price.amount, reverse=False)
    for product in sorted_product[:4]:
        main_price = product.node.price.amount
        comm_price = product.node.price.price_no_commission
        comm_str = ""
        if comm_price is not None and comm_price != main_price:
            comm_str = f" (no comm: {comm_price:.6f})"
        log_parts.append(f"- {product.node.merchant_name}: {main_price:.6f}{comm_str}\n")

    return "".join(log_parts)


# Hàm này là logic thuần túy, không cần async
def get_log_string(
        mode: str,
        payload: Payload,
        final_price: float,
        analysis_result: AnalysisResult = None,
        filtered_products: List[CompetitionEdge] = None
) -> str:
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    log_parts = []
    if mode == "not_compare":
        log_parts = [
            timestamp,
            f"Không so sánh, cập nhật thành công {final_price:.3f}\n"
        ]
    elif mode == "compare":
        log_parts = [
            timestamp,
            f"Cập nhật thành công {final_price:.3f}\n"
        ]
        if analysis_result:
            log_parts.append(_analysis_log_string(payload, analysis_result, filtered_products))
    elif mode == "below_min":
        log_parts = [
            timestamp,
            f"Giá cuối cùng ({final_price:.3f}) nhỏ hơn giá tối thiểu ({payload.get_min_price_value():.3f}), không cập nhật.\n"
        ]
        if analysis_result:
            log_parts.append(_analysis_log_string(payload, analysis_result, filtered_products))
    elif mode == "no_min_price":
        log_parts = [
            timestamp,
            f"Không có min_price, không cập nhật.\n"
        ]
        if analysis_result:
            log_parts.append(_analysis_log_string(payload, analysis_result, filtered_products))
    elif mode == "not_follow":
        log_parts = [
            timestamp,
            f"Giá đang thấp hơn đối thủ hoặc giá max, không cập nhật.\n"
        ]
        if analysis_result:
            log_parts.append(_analysis_log_string(payload, analysis_result, filtered_products))
    elif mode == "equal":
        log_parts = [
            timestamp,
            f"Giá hiện tại không cần chỉnh, không cập nhật\n"
        ]
        if analysis_result:
            log_parts.append(_analysis_log_string(payload, analysis_result, filtered_products))
    return " ".join(log_parts)
