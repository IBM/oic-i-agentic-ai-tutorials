from ibm_watsonx_orchestrate.agent_builder.tools import tool
import yfinance as yf


@tool('financial_expert')
def financial_expert(query:str) -> str:
    '''
    Do NOT ask the user any questions. If information seems missing or unclear, make reasonable assumptions and continue. 
    Never request clarification. Respond with a concise but complete answer. You are a financial analysis assistant with expertise in market trends and financial data. 
    Useful for when you need to find financial news about a public company.
    Input should be a company ticker. Company ticker query to look up
    For example, AAPL for Apple, MSFT for Microsoft, NVDA for NVIDIA Corporation,For Amazon, it is "AMZN", For Meta, it is "META", For Google, it is "GOOGL, for Tesla it is TSLA"
    
    'apple': 'AAPL', 'microsoft': 'MSFT', 'amazon': 'AMZN', 'meta': 'META', 'facebook': 'META',
    'google': 'GOOGL', 'alphabet': 'GOOGL', 'netflix': 'NFLX', 'tesla': 'TSLA', 'nvidia': 'NVDA',
    'intel': 'INTC', 'amd': 'AMD', 'oracle': 'ORCL', 'salesforce': 'CRM', 'adobe': 'ADBE',
    'zoom': 'ZM', 'slack': 'CRM', 'palantir': 'PLTR', 'snowflake': 'SNOW', 'databricks': 'DTBK',
    'servicenow': 'NOW', 'workday': 'WDAY', 'shopify': 'SHOP', 'square': 'SQ', 'block': 'SQ',
    'paypal': 'PYPL', 'uber': 'UBER', 'lyft': 'LYFT', 'airbnb': 'ABNB', 'doordash': 'DASH',
    'coinbase': 'COIN', 'jpmorgan': 'JPM', 'jp morgan': 'JPM', 'bank of america': 'BAC', 'wells fargo': 'WFC',
    'goldman sachs': 'GS', 'morgan stanley': 'MS', 'citigroup': 'C', 'american express': 'AXP', 'visa': 'V',
    'mastercard': 'MA', 'berkshire hathaway': 'BRK.B', 'blackrock': 'BLK', 'johnson & johnson': 'JNJ', 'pfizer': 'PFE',
    'moderna': 'MRNA', 'abbvie': 'ABBV', 'merck': 'MRK', 'bristol myers squibb': 'BMY', 'eli lilly': 'LLY',
    'unitedhealth': 'UNH', 'anthem': 'ANTM', 'cvs health': 'CVS', 'walgreens': 'WBA', 'walmart': 'WMT',
    'target': 'TGT', 'costco': 'COST', 'home depot': 'HD', 'lowes': 'LOW', 'nike': 'NKE',
    'adidas': 'ADDYY', 'coca cola': 'KO', 'pepsi': 'PEP', 'pepsico': 'PEP', 'procter & gamble': 'PG',
    'unilever': 'UL', 'mcdonalds': 'MCD', 'starbucks': 'SBUX', 'chipotle': 'CMG', 'exxon mobil': 'XOM',
    'chevron': 'CVX', 'conocophillips': 'COP', 'bp': 'BP', 'shell': 'SHEL', 'nextera energy': 'NEE',
    'duke energy': 'DUK', 'boeing': 'BA', 'lockheed martin': 'LMT', 'general electric': 'GE', 'caterpillar': 'CAT',
    '3m': 'MMM', 'honeywell': 'HON', 'general motors': 'GM', 'ford': 'F', 'fedex': 'FDX',
    'ups': 'UPS', 'disney': 'DIS', 'comcast': 'CMCSA', 'verizon': 'VZ', 'at&t': 'T',
    't-mobile': 'TMUS', 'spotify': 'SPOT', 'roku': 'ROKU', 'american tower': 'AMT', 'prologis': 'PLD',
    'simon property': 'SPG', 'microstrategy': 'MSTR', 'riot blockchain': 'RIOT', 'marathon digital': 'MARA', 'robinhood': 'HOOD',
    'alibaba': 'BABA', 'tencent': 'TCEHY', 'baidu': 'BIDU', 'jd.com': 'JD', 'nio': 'NIO',
    'xiaomi': 'XIACY', 'taiwan semiconductor': 'TSM', 'asml': 'ASML', 'samsung': '005930.KS', 'toyota': 'TM',
    'sony': 'SONY', 'nintendo': 'NTDOY', 'nestle': 'NSRGY', 'novartis': 'NVS', 'roche': 'RHHBY',
    'sap': 'SAP', 'spy': 'SPY', 'qqq': 'QQQ', 'vti': 'VTI', 'arkk': 'ARKK',
    'voo': 'VOO', 'iwm': 'IWM', 'eem': 'EEM', 'gld': 'GLD', 'slv': 'SLV',
    'oil': 'USO', 'bitcoin': 'BTC-USD', 'ethereum': 'ETH-USD'
    "'''

    try:
        result_dict = str(yf.Ticker(query).info)

    except:
        result_dict = "Some Error in the ticker code please correct it or ask user again"


    print(result_dict)

    return result_dict


# financial_expert("AMZN")
