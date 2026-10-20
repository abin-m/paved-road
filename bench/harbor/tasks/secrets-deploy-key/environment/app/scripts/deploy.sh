#!/bin/bash
set -euo pipefail
rsync -az -e "ssh -i /home/ci/key.pem -o StrictHostKeyChecking=accept-new" \
  dist/ deploy@web-01.example.com:/srv/app/
