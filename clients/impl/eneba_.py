S_PRODUCTS_QUERY = """
    query S_products($search: String, $first: Int) {
        S_products(search: $search, first: $first) {
            edges {
                node {
                    id
                    name
                    isSellable
                }
            }
        }
    }
"""
