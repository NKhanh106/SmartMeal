#!/usr/bin/env python3
"""Comprehensive backend diagnostics for SmartMeal audit."""
import os, sys, subprocess, ast

BASE = r"e:\Tài liệu học\2025-2\Đồ án tốt nghiệp\SmartMeal\apps\api"
os.chdir(BASE)

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

# 1. Test count
print_section("1. PYTEST TEST COUNT")
r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], capture_output=True, text=True)
print("STDOUT:", r.stdout[-3000:] if r.stdout else "(none)")
print("STDERR:", r.stderr[-500:] if r.stderr else "(none)")
print("RC:", r.returncode)

# 2. File/line counts
print_section("2. CODE STATISTICS")
total_files = 0; total_lines = 0
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ('__pycache__', '.pytest_cache', 'node_modules', '.git')]
    for f in files:
        if f.endswith('.py'):
            total_files += 1
            try:
                with open(os.path.join(root, f), 'r', encoding='utf-8') as fp:
                    total_lines += len(fp.readlines())
            except: pass
print(f"Python files: {total_files}")
print(f"Total lines: {total_lines}")
# Count routes
rc = 0; fc = 0
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ('__pycache__', '.pytest_cache')]
    for f in files:
        if f.endswith('.py') and 'api' in root:
            try:
                with open(os.path.join(root, f), 'r', encoding='utf-8') as fp:
                    c = fp.read()
                    rc += c.count('@router.')
                    rc += c.count('@app.')
                    fc += c.count('def ')
            except: pass
print(f"API route decorators: {rc}")
print(f"Functions: {fc}")

# 3. SQL injection patterns
print_section("3. SQL INJECTION CHECK")
issues = []
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ('__pycache__', '.pytest_cache', 'node_modules')]
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try:
                with open(path, 'r', encoding='utf-8') as fp:
                    lines = fp.readlines()
                    for i, line in enumerate(lines, 1):
                        stripped = line.strip()
                        if ('execute' in stripped or 'text(' in stripped) and ('f"' in stripped or "f'" in stripped):
                            issues.append(f"{path}:{i}: {stripped[:120]}")
            except: pass
print(f"Potential f-string SQL: {len(issues)}")
for iss in issues[:10]: print(" ", iss)

# 4. Hardcoded secrets
print_section("4. HARDCODED SECRETS CHECK")
secrets = []
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ('__pycache__', '.pytest_cache', 'node_modules')]
    for f in files:
        if f.endswith('.py') and 'test' not in f:
            path = os.path.join(root, f)
            try:
                with open(path, 'r', encoding='utf-8') as fp:
                    for i, line in enumerate(fp.readlines(), 1):
                        l = line.strip()
                        if any(p in l for p in ['PASSWORD=', 'SECRET_KEY=', 'GROQ_API_KEY=', 'GEMINI_API_KEY=', 'DATABASE_URL=']) and '#' not in l[:10]:
                            val = l.split('=', 1)[1].strip().strip('"\'')
                            if len(val) > 8 and val not in ('None', '[]', '{}', '""', "''", 'ENV('):
                                secrets.append(f"{path}:{i}: {l[:120]}")
            except: pass
print(f"Potential hardcoded secrets: {len(secrets)}")
for s in secrets[:15]: print(" ", s)

# 5. Dockerfile security
print_section("5. DOCKERFILE SECURITY")
try:
    with open('Dockerfile', 'r', encoding='utf-8') as f:
        dc = f.read()
    checks = {
        'No root (USER set)': 'USER ' in dc or 'RUN useradd' in dc,
        'HEALTHCHECK': 'HEALTHCHECK' in dc,
        'No :latest tag': ':latest' not in dc,
        'Python version': 'python:3' in dc,
    }
    for k, v in checks.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
except Exception as e:
    print(f"  Error: {e}")

# 6. Auth-gated endpoints
print_section("6. AUTH-GATED ENDPOINTS")
auth_gated = 0; rate_limited = 0; public = 0
for root, dirs, files in os.walk('app/api'):
    for f in files:
        if f.endswith('.py') and f != '__init__.py' and 'deps' not in f:
            try:
                with open(os.path.join(root, f), 'r', encoding='utf-8') as fp:
                    c = fp.read()
                    auth_gated += c.count('Depends(get_current_user)')
                    auth_gated += c.count('Depends(get_current_active_user)')
                    rate_limited += c.count('@limiter.limit')
                    public += c.count('Depends(lambda: None)')
            except: pass
print(f"  Auth-gated (Depends on user): {auth_gated}")
print(f"  Rate-limited: {rate_limited}")
print(f"  Public: {public}")

# 7. DB commit patterns
print_section("7. DB COMMIT PATTERNS")
commits = []; adds = 0
for root, dirs, files in os.walk('app'):
    dirs[:] = [d for d in dirs if d not in ('__pycache__', '.pytest_cache', 'migrations')]
    for f in files:
        if f.endswith('.py') and 'test' not in f:
            try:
                with open(os.path.join(root, f), 'r', encoding='utf-8') as fp:
                    c = fp.read()
                    for i, line in enumerate(c.split('\n'), 1):
                        if 'await db.commit()' in line or 'await session.commit()' in line:
                            commits.append(f"{os.path.join(root,f)}:{i}")
                    if 'api' in root:
                        adds += c.count('db.add(')
            except: pass
print(f"  DB commit statements: {len(commits)}")
print(f"  db.add() in API layer: {adds}")

# 8. Circuit breaker usage
print_section("8. CIRCUIT BREAKER & RESILIENCE")
cb_files = []
for root, dirs, files in os.walk('app'):
    dirs[:] = [d for d in dirs if d not in ('__pycache__', '.pytest_cache')]
    for f in files:
        if f.endswith('.py'):
            try:
                with open(os.path.join(root, f), 'r', encoding='utf-8') as fp:
                    if 'circuit_breaker' in fp.read():
                        cb_files.append(os.path.join(root, f))
            except: pass
print(f"  Files using circuit_breaker: {len(cb_files)}")
for f in cb_files: print(f"    {f}")

# 9. Agent system components
print_section("9. MULTI-AGENT SYSTEM")
agent_files = []
for root, dirs, files in os.walk('app/agents'):
    for f in files:
        if f.endswith('.py') and f != '__init__.py':
            try:
                with open(os.path.join(root, f), 'r', encoding='utf-8') as fp:
                    c = fp.read()
                    if 'class ' in c and 'Agent' in c:
                        agent_files.append(f)
            except: pass
print(f"  Agent class files: {len(agent_files)}")
for f in agent_files: print(f"    {f}")

# 10. Depth mode configuration
print_section("10. DEPTH MODE CONFIGURATION")
try:
    with open('app/agents/depth_config.py', 'r', encoding='utf-8') as f:
        dc = f.read()
    modes = ['QUICK', 'quick', 'DEEP', 'deep', 'EXPERT', 'expert']
    found = [m for m in modes if m in dc]
    print(f"  Depth modes found: {found}")
    print(f"  DEPTH_CONFIGS dict: {'YES' if 'DEPTH_CONFIGS' in dc else 'NO'}")
    print(f"  get_depth_config fn: {'YES' if 'def get_depth_config' in dc else 'NO'}")
    print(f"  ResponseDepth enum: {'YES' if 'ResponseDepth' in dc else 'NO'}")
except Exception as e:
    print(f"  Error: {e}")

# 11. Write-back system
print_section("11. WRITE-BACK SYSTEM")
wb_files = []
for root, dirs, files in os.walk('app'):
    dirs[:] = [d for d in dirs if d not in ('__pycache__', '.pytest_cache', 'migrations')]
    for f in files:
        if f.endswith('.py'):
            try:
                with open(os.path.join(root, f), 'r', encoding='utf-8') as fp:
                    c = fp.read()
                    if 'UpdateProposal' in c or 'execute_confirmed_update' in c:
                        wb_files.append(os.path.join(root, f))
            except: pass
print(f"  Files in WriteBack system: {len(wb_files)}")
for f in wb_files: print(f"    {f}")
# Check Redis for proposals
try:
    with open('app/api/v1/ai_chatbot.py', 'r', encoding='utf-8') as f:
        chat = f.read()
    print(f"  getdel in confirm: {'YES' if 'getdel' in chat else 'NO'}")
    print(f"  redis.setex for proposals: {'YES' if 'setex' in chat else 'NO'}")
    print(f"  proposal: key prefix: {'YES' if 'proposal:' in chat else 'NO'}")
except Exception as e:
    print(f"  Error: {e}")

# 12. Context loader
print_section("12. CONTEXT ENGINEERING")
try:
    with open('app/agents/context_loader.py', 'r', encoding='utf-8') as f:
        cl = f.read()
    checks = {
        'asyncio.gather': 'asyncio.gather' in cl,
        'FullUserContext': 'FullUserContext' in cl,
        'BodySnapshotData': 'BodySnapshotData' in cl,
        'NutritionSnapshot': 'NutritionSnapshot' in cl,
        'FitnessSnapshotData': 'FitnessSnapshotData' in cl,
        'load_full_user_context': 'def load_full_user_context' in cl,
    }
    for k, v in checks.items():
        print(f"  {k}: {'YES' if v else 'NO'}")
except Exception as e:
    print(f"  Error: {e}")

# 13. Migrations
print_section("13. MIGRATION COUNT")
try:
    files = [f for f in os.listdir('migrations/versions') if f.endswith('.py')]
    print(f"  Migration files: {len(files)}")
    for f in sorted(files):
        if f not in ('__init__.py', 'README', 'script.py.mako'):
            print(f"    {f}")
except Exception as e:
    print(f"  Error: {e}")

# 14. Redis usage
print_section("14. REDIS USAGE")
redis_files = []
for root, dirs, files in os.walk('app'):
    dirs[:] = [d for d in dirs if d not in ('__pycache__', '.pytest_cache')]
    for f in files:
        if f.endswith('.py'):
            try:
                with open(os.path.join(root, f), 'r', encoding='utf-8') as fp:
                    c = fp.read()
                    if 'redis' in c or 'get_redis' in c or 'Redis' in c:
                        redis_files.append(os.path.join(root, f))
            except: pass
print(f"  Files using Redis: {len(redis_files)}")
for f in redis_files: print(f"    {f}")

# 15. Security features
print_section("15. SECURITY FEATURES")
checks = {}
try:
    with open('app/api/v1/auth.py', 'r', encoding='utf-8') as f:
        ac = f.read()
    checks['refresh token rotation'] = 'revoked_refresh' in ac or 'token_hash' in ac
    checks['bcrypt'] = 'CryptContext' in ac
    checks['JWT expiration'] = 'ACCESS_TOKEN_EXPIRE' in ac
    checks['soft delete field'] = 'deleted_at' in ac
except: pass
try:
    with open('app/core/rate_limiter.py', 'r', encoding='utf-8') as f:
        rl = f.read()
    checks['X-Forwarded-For'] = 'X-Forwarded-For' in rl
except: pass
try:
    with open('app/core/sanitize.py', 'r', encoding='utf-8') as f:
        sc = f.read()
    checks['sanitize_for_prompt'] = 'def sanitize_for_prompt' in sc
except: pass
try:
    with open('app/core/token_budget.py', 'r', encoding='utf-8') as f:
        tb = f.read()
    checks['truncate_to_token_budget'] = 'def truncate_to_token_budget' in tb
except: pass
for k, v in checks.items():
    print(f"  {k}: {'PRESENT' if v else 'MISSING'}")

# 16. Rate limiter health check
print_section("16. HEALTH ENDPOINT")
try:
    with open('app/api/v1/health.py', 'r', encoding='utf-8') as f:
        hc = f.read()
    print(f"  Routes defined: {'YES' if '@router' in hc else 'NO'}")
    print(f"  Circuit breaker check: {'YES' if 'circuit' in hc.lower() else 'NO'}")
    print(f"  Redis check: {'YES' if 'redis' in hc.lower() or 'Redis' in hc else 'NO'}")
except Exception as e:
    print(f"  Error: {e}")

# 17. Models check
print_section("17. MODEL COUNTS")
model_count = 0
for root, dirs, files in os.walk('app/models'):
    for f in files:
        if f.endswith('.py') and f != '__init__.py':
            model_count += 1
print(f"  Model files: {model_count}")

# 18. Schema count
print_section("18. SCHEMA COUNTS")
schema_count = 0
for root, dirs, files in os.walk('app/schemas'):
    for f in files:
        if f.endswith('.py') and f != '__init__.py':
            schema_count += 1
print(f"  Schema files: {schema_count}")

# 19. API v1 endpoints
print_section("19. API V1 ENDPOINT FILES")
ep_files = []
for root, dirs, files in os.walk('app/api/v1'):
    for f in files:
        if f.endswith('.py') and f != '__init__.py' and f != 'deps.py':
            ep_files.append(f)
print(f"  Endpoint files: {len(ep_files)}")
for f in sorted(ep_files): print(f"    {f}")

# 20. Service count
print_section("20. SERVICE COUNT")
svc_count = 0
for root, dirs, files in os.walk('app/services'):
    for f in files:
        if f.endswith('.py') and f != '__init__.py':
            svc_count += 1
print(f"  Service files: {svc_count}")

print(f"\n{'='*60}")
print("  DIAGNOSTICS COMPLETE")
print('='*60)
