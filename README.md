# Instagram video → Slack

Pings a Slack channel whenever a new video or Reel is posted to your Instagram
account. Runs free on GitHub Actions, checking every 10 minutes.

## What you need

- An Instagram **Business or Creator** account (no Facebook Page required)
- A GitHub account
- Permission to add apps to your Slack workspace

## 1. Get a Slack webhook URL

1. Go to https://api.slack.com/apps → **Create New App** → **From scratch**. Name it
   (e.g. "Instagram Alerts") and pick your workspace.
2. In the sidebar, open **Incoming Webhooks** and switch it **On**.
3. Click **Add New Webhook**, choose the channel for the pings, and allow it.
4. Copy the webhook URL (starts with `https://hooks.slack.com/services/...`).

## 2. Get an Instagram access token

1. Go to https://developers.facebook.com/apps → **Create App**. Choose the use case
   for managing content/messaging on **Instagram**, and a **Business** app type if asked.
2. In the app dashboard, open the Instagram product's **API setup with Instagram
   login** page.
3. Under **Generate access tokens**, click **Add account** and log in with your
   Instagram account. If it asks you to accept a tester invite, do so in the
   Instagram app (Settings → Website permissions → Apps and websites → Tester invites).
4. Click **Generate token** next to the account and copy it. It's valid for 60
   days, and the refresh workflow below keeps it alive automatically.

You can leave the Meta app in development mode; it only needs to read your own account.

## 3. Set up the GitHub repo

1. Create a new **public** repository and upload these files, keeping the
   `.github/workflows/` folder structure.
   *Why public:* Actions minutes are free and unlimited on public repos. Only the
   code and a list of post IDs are visible; your tokens stay secret. If you'd rather
   use a private repo, change the cron in `instagram-to-slack.yml` to `*/30 * * * *`
   to stay within the 2,000 free minutes a month.
2. Create a GitHub token so the refresh workflow can update the Instagram secret:
   GitHub → Settings → Developer settings → **Fine-grained tokens** → Generate.
   Give it access to **only this repository**, with the **Secrets: Read and write**
   permission. Pick the longest expiration you're comfortable with, and note the date.
3. In the repo, go to **Settings → Secrets and variables → Actions** and add three
   repository secrets:

   | Name                | Value                         |
   |---------------------|-------------------------------|
   | `IG_ACCESS_TOKEN`   | Instagram token from step 2   |
   | `SLACK_WEBHOOK_URL` | Slack webhook from step 1     |
   | `GH_PAT`            | GitHub token from above       |

4. Optional: to also ping for carousels that contain a video, add a repository
   **variable** (Variables tab) named `INCLUDE_CAROUSELS` with the value `true`.

## 4. Test it

1. Go to the **Actions** tab and enable workflows if prompted.
2. Open **Instagram video → Slack** → **Run workflow**, tick
   **"Send the most recent video to Slack right now"**, and run it.
   You should get a ping for your latest video. This first run also saves your
   existing posts to `state.json` so old videos don't trigger pings.
3. Open **Refresh Instagram token** → **Run workflow** once to confirm the token
   refresh works. (It fails if the token is less than 24 hours old, so try again
   the next day if needed.)

From now on, new videos show up in Slack within roughly 10–15 minutes of posting.

## Troubleshooting

- **"Instagram API error 190"**: the token expired or is invalid. Generate a new one
  (step 2) and update the `IG_ACCESS_TOKEN` secret.
- **Refresh workflow fails with 403 on `gh secret set`**: the `GH_PAT` is missing the
  Secrets read/write permission, or it has expired.
- **"Slack error 404 / no_service"**: the webhook was removed. Make a new one and
  update `SLACK_WEBHOOK_URL`.
- **Push rejected in "Save state"**: under Settings → Actions → General → Workflow
  permissions, choose **Read and write permissions**.
- Stories aren't included; Instagram's API doesn't expose them this way.
