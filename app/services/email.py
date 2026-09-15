from datetime import datetime

def get_password_reset_template(reset_link: str) -> str:
    current_year = datetime.now().year
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Reset your password</title>
      <style>
        @media only screen and (max-width: 600px) {{
          .email-container {{ width: 100% !important; border-radius: 0 !important; }}
          .content-cell {{ padding: 30px 20px !important; }}
          .logo-cell {{ padding: 30px 20px 20px !important; }}
          .heading {{ font-size: 18px !important; }}
          .text-body {{ font-size: 14px !important; }}
          .button {{ font-size: 14px !important; padding: 12px 24px !important; width: 100% !important; box-sizing: border-box !important; text-align: center !important; }}
        }}
      </style>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f3f4f6; margin: 0; padding: 20px 0;">
      <table width="100%" cellpadding="0" cellspacing="0" class="email-container" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);">
        <tr>
          <td class="logo-cell" style="padding: 40px 40px 20px; text-align: center; border-bottom: 1px solid #f3f4f6;">
            <!-- REPLACE THE SRC ATTRIBUTE WITH THE URL TO YOUR HOSTED PNG LOGO -->
            <img src="https://bazzix-ai.vercel.app/logo.png" alt="Bazzix" width="120" style="display: block; margin: 0 auto; font-family: sans-serif; font-size: 24px; font-weight: bold; color: #111827; text-decoration: none;" border="0">
          </td>
        </tr>
        <tr>
          <td class="content-cell" style="padding: 40px;">
            <h2 class="heading" style="margin: 0 0 16px; color: #1f2937; font-size: 20px; font-weight: 600;">Reset your password</h2>
            <p class="text-body" style="margin: 0 0 24px; color: #4b5563; font-size: 16px; line-height: 1.6;">
              We received a request to reset the password for your Bazzix account. If you didn't make this request, you can safely ignore this email.
            </p>
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td align="center">
                  <a href="{reset_link}" class="button" style="display: inline-block; background-color: #2563eb; color: #ffffff; font-size: 16px; font-weight: 600; text-decoration: none; padding: 14px 28px; border-radius: 8px;">
                    Reset Password
                  </a>
                </td>
              </tr>
            </table>
            <p class="text-body" style="margin: 32px 0 0; color: #6b7280; font-size: 14px; line-height: 1.5;">
              If the button doesn't work, copy and paste this link into your browser:<br>
              <a href="{reset_link}" style="color: #2563eb; text-decoration: underline; word-break: break-all; display: inline-block; margin-top: 4px;">{reset_link}</a>
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding: 24px 40px; background-color: #f9fafb; text-align: center;">
            <p style="margin: 0; color: #9ca3af; font-size: 12px;">
              &copy; {current_year} Bazzix. All rights reserved.
            </p>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """
