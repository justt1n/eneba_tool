import logging

from clients.impl.eneba_client import EnebaClient
from services.eneba_service import EnebaService

if __name__ == "__main__":
    eneba_service = EnebaService(
        eneba_client=EnebaClient()
    )

    _id = eneba_service.get_product_id_by_slug("psn-playstation-network-card-250-usd-usa-psn-key-united-states")
    price_result = eneba_service.calculate_commission_price(
        prodId=str(_id),
        amount=250,
    )
    print(price_result.model_dump_json())
    # print(_id)
    # # products = eneba_service.get_competition_by_product_id(_id)
    # products = eneba_service.get_competition_by_slug("psn-playstation-network-card-250-usd-usa-psn-key-united-states")
    # products.sort(key=lambda x: x.node.price.amount, reverse=False)
    # for product in products:
    #     print(f"Merchant: {product.node.merchant_name}, Price: {product.node.price.amount} {product.node.price.currency}, In Stock: {product.node.is_in_stock}")


