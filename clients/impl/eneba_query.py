S_PRODUCTS_BY_SLUGS_QUERY = """
    query S_productsBySlugs($slugs: [String!], $sort: S_API_ProductsSort, $first: Int) {
        S_products(slugs: $slugs, sort: $sort, first: $first) {
            edges {
                node {
                    id
                    name
                    slug
                    isSellable
                }
            }
        }
    }
"""

S_COMPETITION_QUERY = """
        query S_competition($productIds: [S_Uuid!]!) {
            S_competition(productIds: $productIds) {
                productId
                competition {
                    totalCount
                    edges {
                        node {
                            isInStock
                            merchantName
                            belongsToYou
                            price(currency: eur) {
                                amount
                                currency
                            }
                        }
                    }
                }
            }
        }
    """

S_CALCULATE_PRICE_QUERY = """
    query S_calculatePrice($input: S_API_CalculatePriceInput!) {
        S_calculatePrice(input: $input) {
            priceWithCommission {
                amount
                currency
            }
            priceWithoutCommission {
                currency
                amount
            }
        }
    }
"""
