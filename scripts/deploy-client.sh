#!/bin/bash
set -e

CLIENT=$1
if [ -z "$CLIENT" ]; then
  echo "Usage: ./scripts/deploy-client.sh <client-slug>"
  echo "Example: ./scripts/deploy-client.sh crystal-metamorphose-fr"
  exit 1
fi

ENV_FILE=".env.clients/${CLIENT}.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "Error: $ENV_FILE not found"
  echo "Create it with: VITE_API_URL, VITE_CLIENT_TOKEN, SSH_USER, SSH_HOST, SSH_PATH"
  exit 1
fi

source "$ENV_FILE"

echo "Building for client: $CLIENT"
VITE_API_URL="$VITE_API_URL" \
VITE_CLIENT_TOKEN="$VITE_CLIENT_TOKEN" \
VITE_CLIENT_SLUG="$CLIENT" \
npm run build --prefix client

echo "Deploying to $SSH_USER@$SSH_HOST:$SSH_PATH"
rsync -avz --delete client/dist/ "$SSH_USER@$SSH_HOST:$SSH_PATH"

echo "Writing .htaccess"
scp scripts/htaccess.template "$SSH_USER@$SSH_HOST:$SSH_PATH/.htaccess"

echo "Done: check your DNS for seo subdomain on ${CLIENT}"
