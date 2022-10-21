import san.sanbase_graphql
from san.sanbase_graphql_helper import QUERY_MAPPING
from san.graphql import execute_gql, get_response_headers
from san.query import get_gql_query, parse_dataset
from san.transform import transform_query_result
from san.error import SanError

CUSTOM_QUERIES = {
    'ohlcv': 'get_ohlcv'
}

DEPRECATED_QUERIES = {
    'mvrv_ratio': 'mvrv_usd',
    'nvt_ratio': 'nvt',
    'realized_value': 'realized_value_usd',
    'token_circulation': 'circulation_1d',
    'burn_rate': 'age_destroyed',
    'token_age_consumed': 'age_destroyed',
    'token_velocity': 'velocity',
    'daily_active_deposits': 'active_deposits',
    'social_volume': 'social_volume_{source}',
    'social_dominance': 'social_dominance_{source}'
}

NO_SLUG_QUERIES = [
    'social_volume_projects',
    'emerging_trends',
    'top_social_gainers_losers'
]


def get(dataset, **kwargs):
    """
    The old way of using the `get` funtion is to provide the metric and slug
    as a single string. This requires string interpolation.
    
    Example: 
    
    san.get(
        "daily_active_addresses/bitcoin"
        from_date="2020-01-01"
        to_date="2020-01-10")
    
    The new and preferred way is to provide the slug as a separate parameter.
    
    This allows more flexible selectors to be used instead of a single strings.
    Examples:

    san.get(
        "daily_active_addresses",
        slug="bitcoin",
        from_date="2020-01-01"
        to_date="2020-01-10")

    san.get(
        "dev_activity",
        selector={"organization": "ethereum"},
        from_date="utc_now-60d",
        to_date="utc_now-40d")
    """
    query, slug = parse_dataset(dataset)
    if slug or query in NO_SLUG_QUERIES:
        return __get_metric_slug_string_selector(query, slug, dataset, **kwargs)
    elif query and not slug:
        return __get(query, **kwargs)


def is_rate_limit_exception(exception):
    return 'API Rate Limit Reached' in str(exception)


def rate_limit_time_left(exception):
    words = str(exception).split()
    return int(list(filter(lambda x: x.isnumeric(), words))[0]) # Message is: API Rate Limit Reached. Try again in X seconds (<human readable time>)  


def api_calls_remaining():
    gql_query_str = san.sanbase_graphql.get_api_calls_made()
    res = get_response_headers(gql_query_str)
    return __get_headers_remaining(res)


def api_calls_made():
    gql_query_str = san.sanbase_graphql.get_api_calls_made()
    res = __request_api_call_data(gql_query_str)
    api_calls = __parse_out_calls_data(res)

    return api_calls


def __request_api_call_data(query):
    try:
        res = execute_gql(query)['currentUser']['apiCallsHistory']
    except Exception as exc:
        if 'the results are empty' in str(exc):
            raise SanError('No API Key detected...')
        else:
            raise SanError(exc)

    return res


def __get_metric_slug_string_selector(query, slug, dataset, **kwargs):
    if query in DEPRECATED_QUERIES:
        print(
            '**NOTICE**\n{} will be deprecated in version 0.9.0, please use {} instead'.format(
                query, DEPRECATED_QUERIES[query]))
    if query in CUSTOM_QUERIES:
        return getattr(san.sanbase_graphql, query)(0, slug, **kwargs)
    if query in QUERY_MAPPING.keys():
        gql_query = '{' + get_gql_query(0, dataset, **kwargs) + '}'
    else:
        if slug != '':
            gql_query = '{' + \
                san.sanbase_graphql.get_metric(0, query, slug, **kwargs) + '}'
        else:
            raise SanError('Invalid metric!')
    res = execute_gql(gql_query)

    return transform_query_result(0, query, res)


def __get(query, **kwargs):
    if not ('selector' in kwargs or 'slug' in kwargs):
        raise SanError('''
            Invalid call of the get function,you need to either
            give <metric>/<slug> as a first argument or give a slug
            or selector as a key-word argument!''')
    gql_query = '{' + san.sanbase_graphql.get_metric(0, query, **kwargs) + '}'
    res = execute_gql(gql_query)

    return transform_query_result(0, query, res)

def __parse_out_calls_data(response):
    try:
        api_calls = list(map(
            lambda x: (x['datetime'], x['apiCallsCount']), response
        ))
    except:
        raise SanError('An error has occured, please contact our support...')

    return api_calls


def __get_headers_remaining(data):
    try:
        return {
            'month_remaining': data['x-ratelimit-remaining-month'],
            'hour_remaining': data['x-ratelimit-remaining-hour'],
            'minute_remaining': data['x-ratelimit-remaining-minute']
        }
    except KeyError as exc:
        raise SanError('There are no limits for this API Key.')
