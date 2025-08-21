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
                            price(currency: usd) {
                                amount
                                currency
                            }
                        }
                    }
                }
            }
        }
    """