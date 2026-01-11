# 0xMeta Crypto News Aggregator

A production-grade crypto news aggregation API that combines RSS feeds + Twitter(X), categorizes content using GAME X AI agents, and monetizes endpoints using X402 payment protocol with 0xmeta facilitator.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  /news   │  │ X402 Paywall│  │ CORS/Logging│         │
│  │  Endpoints  │──│  Middleware │──│  Middleware │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Controllers  │   │   Services   │   │    Agents    │
│              │   │              │   │              │
│ • News    │   │ • RSS │   │ • Categorizer│
│ • Business   │   │ • GAME X     │   │ • Date Norm  │
│   Logic      │   │ • Payment    │   │ • Data Merger│
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│    Cache     │  │   Database   │  │    Queue     │
│              │  │              │  │              │
│ Redis (1hr)  │  │ Neon Postgres│  │  Dramatiq    │
│ • Trends     │  │ • Signals    │  │ • Async Save │
│ • Feeds      │  │ • Categories │  │ • Processing │
└──────────────┘  └──────────────┘  └──────────────┘
```

## 📁 Project Structure

```
0xmeta-crypto-aggregator/
├── app/
│   ├── agents/              # AI-powered data processing
│   │   ├── categorizer.py   # Content categorization engine
│   │   ├── date_normalizer.py
│   │   └── game_worker.py   # GAME X SDK integration
│   │
│   ├── cache/               # Redis caching layer
│   │   └── redis_client.py
│   │
│   ├── controllers/         # Business logic layer
│   │   └── news_controller.py
│   │
│   ├── core/                # Configuration & utilities
│   │   ├── config.py        # Settings management
│   │   ├── logging.py       # Structured logging
│   │   └── startup.py       # Health checks
│   │
│   ├── database/            # Database layer
│   │   ├── migrations/
│   │   │   └── 001_initial_schema.sql
│   │   └── session.py       # Async SQLAlchemy
│   │
│   ├── middleware/          # Request/response processing
│   │   └── x402.py          # Payment verification
│   │
│   ├── models/              # Data models
│   │   ├── news.py          # Signal & category models
│   │   └── payment.py       # Payment tracking
│   │
│   ├── queue/               # Background jobs
│   │   ├── tasks.py         # Async task definitions
│   │   └── worker.py        # Dramatiq configuration
│   │
│   ├── routes/              # API endpoints
│   │   └── news.py       # News data routes
│   │
│   ├── services/            # External integrations
│   │   ├── rss.py    # RSS (Really Simple Syndication) API client
│   │   └── game_x.py        # GAME X SDK wrapper
│   │
│   ├── workers/             # Scheduled jobs
│   │   └── cleanup.py       # 24hr data cleanup
│   │
│   └── main.py              # FastAPI application
│
├── .env                     # Environment variables
├── pyproject.toml          # Dependencies (uv)
├── Dockerfile              # Container image
└── README.md               # This file
```

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL (Neon)
- Redis
- uv package manager

### Installation

### Prerequisites

- Python 3.14+
- PostgreSQL 13+
- Redis 6+

### Setup

1. **Clone the repository**:

```bash
git clone <repository-url>
cd 0xmeta-merchant
```

2. **Install dependencies**:

```bash
uv sync.
```

3. **Configure environment variables**:

```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Run database migrations**:

```bash
alembic upgrade head
```

5. **Start the server**:

```bash
uv run -m app.main
```

### Environment Variables

```bash
# API Configuration
BASE_URL=http://localhost:8080
FACILITATOR_URL=https://facilitator.0xmeta.ai

# External APIs
GAME_API_KEY=your_game_api_key
GAME_ACCESS_TOKEN=your_game_access_token

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host/db

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_TTL=3600

# Worker
DRAMATIQ_REDIS_URL=redis://localhost:6379/1

# Payment (X402)
PAYMENT_NETWORK=base-sepolia
MERCHANT_PAYOUT_WALLET=0x...
MERCHANT_PRIVATE_KEY=0x... # USDC contract
```

### Running the Application

```bash
# Start Redis
redis-server

# Run database migrations
psql $DATABASE_URL -f app/database/migrations/001_initial_schema.sql

# Start Dramatiq worker (in separate terminal)
uv run dramatiq app.queue.tasks -p 4 -t 4
```

### Docker Deployment

```bash
# Build image
docker build -t 0xmeta-aggregator .

# Run with docker-compose
docker-compose up -d
```

## 📡 API Endpoints

All endpoints require X402 payment (0.01 USDC + 0.01 USDC facilitator fee = 0.02 USDC total)

### Base Endpoint

#### `GET /`

**Description:** Returns API status and information.
**Response:**

```json
{
  "service": "0xmeta.ai",
  "description": "Real-time crypto news aggregation API",
  "version": "1.0.0",
  "docs": "/docs",
  "status": "OK"
}
```

### News Endpoints

#### `GET /news/${category}`

**Description:** Trending crypto news and social updates  
**Price:** 0.01 USDC  
**Cache:** 1 hour  
**Response:**

```json
{
  "trends": {
    "items": [
      {
        "id": "uuid",
        "signal": "Bitcoin surges past $50k...",
        "sentiment": "bullish",
        "sentiment_value": 0.85,
        "timestamp": 1234567890.123,
        "feed_categories": ["bitcoin", "trends"],
        "sources": ["https://..."],
        "author": "CoinDesk",
        "tokens": ["$BTC"]
      }
    ]
  },
  "_metadata": {
    "total_items": 50,
    "timestamp": 1234567890,
    "cache_ttl": 3600
  }
}
```

**Price:** 0.01 USDC

#### `GET /markets/macro_events`

**Description:** Regulatory, institutional, and macro economic news  
**Price:** 0.01 USDC

#### `GET /markets/proof_of_work`

**Description:** Mining, hashrate, and PoW blockchain updates  
**Price:** 0.01 USDC

## 💰 X402 Payment Flow

### 2. Generate Payment Authorization

Frontend uses wallet (MetaMask, WalletConnect) to sign EIP-3009 authorization:

```javascript
const authorization = {
  from: userAddress,
  to: recipientAddress,
  value: "10000", // 0.01 USDC (6 decimals)
  validAfter: Math.floor(Date.now() / 1000),
  validBefore: Math.floor(Date.now() / 1000) + 3600,
  nonce: randomHex64()
};

const signature = await wallet.signTypedData(...);
```

### 3. Make Paid Request

```bash
curl -H "X-Payment: <base64_encoded_payment>" \
     http://localhost:8080/news/${category}
```

**Flow:**

1. **Verify** - 1Shot API validates signature
2. **Return Data** - API responds immediately
3. **Settle** - Transaction submitted async to blockchain

## 🤖 AI Agent System

### GAME X Worker

Uses official GAME SDK to coordinate aggregation:

```python
worker = Worker(
    api_key=GAME_API_KEY,
    description="Crypto news aggregator",
    instruction="Merge and categorize crypto content...",
    action_space=[
        merge_news_and_tweets,
        search_by_keywords,
        get_categorized_feed
    ]
)
```


## 🔄 Background Processing

### Dramatiq Tasks

**save_signal_items** - Persist signals to DB (async)  
**save_category_feed** - Update category caches  
**process_and_merge_feeds** - Scheduled aggregation  
**cleanup_old_signals** - Remove 24hr+ old data

### Scheduled Jobs (APScheduler)

**Cleanup Worker** - Runs hourly

- Deletes signals > 24 hours old
- Cleans category feeds
- Purges old payment records

## 📊 Data Models

### SignalItem

```python
{
  "id": "uuid",
  "signal": "text content",
  "sentiment": "bullish|bearish|neutral",
  "sentiment_value": 0.0-1.0,
  "timestamp": float,
  "feed_categories": ["category1", "category2"],
  "sources": ["url1", "url2"],
  "author": "source name",
  "tokens": ["$BTC", "$ETH"]
}
```

### CategoryFeed

```python
{
  "category": "trends",
  "items": [SignalItem],
  "item_count": 50,
  "last_updated": timestamp
}
```

## 🔒 Security Features

- **X402 Payment Verification** - EIP-3009 signature validation
- **Rate Limiting** - Per-endpoint payment required
- **Input Validation** - Pydantic models for all data
- **SQL Injection Protection** - SQLAlchemy ORM
- **CORS Configuration** - Controlled origin access
- **TLS/HTTPS** - Encrypted data transmission

## 📈 Performance Optimizations

1. **Redis Caching** - 1hr TTL reduces API calls by 90%
2. **Async Database** - AsyncPG for non-blocking queries
3. **Background Processing** - Dramatiq offloads DB writes
4. **Connection Pooling** - Reuses DB connections
5. **Payment Verification** - Cached validation results

## 🐛 Troubleshooting

### Common Issues

**Redis Connection Failed**

```bash
# Check Redis is running
redis-cli ping

# Verify connection string
echo $REDIS_URL
```

**Database Migration Error**

```bash
# Manually run migrations
psql $DATABASE_URL -f app/database/migrations/001_initial_schema.sql
```

**Payment Verification Failed**

- Check `MERCHANT_PRIVATE_KEY` matches network
- Verify `MERCHANT_PAYOUT_WALLET` is correct
- Ensure wallet has USDC approval

**GAME X API Errors**

- Validate `GAME_API_KEY` and `GAME_ACCESS_TOKEN`
- Check API quota limits
- Review Twitter account permissions

## 📝 Development Guidelines

### Code Style

- **Black** for formatting
- **Ruff** for linting
- **Type hints** for all functions
- **Docstrings** for public APIs

### Git Workflow

```bash
# Feature branch
git checkout -b feature/your-feature

# Commit with conventional commits
git commit -m "feat: add new endpoint"

# Push and create PR
git push origin feature/your-feature
```

### Adding New Endpoints

1. Define route in `app/routes/markets.py`
2. Add controller method in `app/controllers/`
3. Update X402 payment config
4. Add tests in `tests/`
5. Update this README

## 🚢 Deployment

### Production Checklist

- [ ] Set `APP_ENV=production`
- [ ] Use production database (not dev/test)
- [ ] Configure Redis persistence
- [ ] Set up monitoring (Sentry, DataDog)
- [ ] Enable HTTPS/TLS
- [ ] Configure backup strategy
- [ ] Set resource limits (CPU/memory)
- [ ] Review security headers
- [ ] Test payment flow end-to-end
- [ ] Load test API endpoints

### Environment-Specific Configs

**Development**

```bash
DEBUG=1
LOG_LEVEL=DEBUG
REDIS_TTL=300  # 5min for faster testing
```

**Production**

```bash
DEBUG=0
LOG_LEVEL=INFO
REDIS_TTL=3600
SHOW_SQL_ALCHEMY_QUERIES=0
```

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [GAME X SDK Docs](https://docs.game.virtuals.io)
- [X402 Protocol Spec](https://docs.0xmeta.ai)
- [EIP-3009 Standard](https://eips.ethereum.org/EIPS/eip-3009)

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request
5. Await code review

## 📄 License

MIT License - see LICENSE file

## 👥 Support

- **Issues:** GitHub Issues
- **Email:** support@0xmeta.ai
- **Discord:** [Join our server](#)

---

**Built with ❤️ by the 0xMeta team**
