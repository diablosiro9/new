#!/bin/bash
# demo_taskmaster.sh

TASKMASTER="./run_taskmaster.sh"
CONFIG="example_config.yaml"

echo "=== DEMO TASKMASTER ==="

# 1. Lancer TaskMaster
echo "1️⃣ Lancement TaskMaster en foreground..."
$TASKMASTER start &
TM_PID=$!
sleep 1

# 2. Status
echo "2️⃣ Status init..."
echo "status" | nc localhost 12345 || true
sleep 1

# 3. Kill un processus unexpected
PROG_PID=$(ps -ef | grep sleep_test | grep -v grep | awk '{print $2}')
echo "3️⃣ Killing sleep_test PID=$PROG_PID ..."
kill -9 $PROG_PID
sleep 2

# 4. Vérifier restart automatique
echo "4️⃣ Status après kill (should restart)..."
echo "status" | nc localhost 12345 || true
sleep 1

# 5. Stop manuel
echo "5️⃣ Stop manuel..."
echo "stop sleep_test" | nc localhost 12345 || true
sleep 1

# 6. Reload config
echo "6️⃣ Reload config..."
kill -HUP $TM_PID
sleep 1

# 7. Status final
echo "7️⃣ Status final..."
echo "status" | nc localhost 12345 || true

# 8. Stop TaskMaster
echo "8️⃣ Stop TaskMaster..."
kill -TERM $TM_PID
sleep 1
echo "✅ Demo terminée."
