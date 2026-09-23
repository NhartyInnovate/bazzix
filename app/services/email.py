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


def get_welcome_template(dashboard_link: str, frontend_url: str) -> str:
    current_year = datetime.now().year
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Welcome to Bazzix</title>
      <style>
        @media only screen and (max-width: 600px) {{
          .email-container {{ width: 100% !important; }}
          .content-cell {{ padding: 30px 20px !important; }}
          .heading {{ font-size: 26px !important; }}
          .button {{ font-size: 14px !important; padding: 12px 24px !important; width: 100% !important; box-sizing: border-box !important; text-align: center !important; }}
          .footer-cell {{ padding: 20px !important; }}
        }}
      </style>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8f9fa; margin: 0; padding: 40px 0;">
      <table width="100%" cellpadding="0" cellspacing="0" class="email-container" style="max-width: 600px; margin: 0 auto; background-color: #ffffff;">
        <tr>
          <td class="content-cell" style="padding: 40px 40px 20px;">
            <h1 class="heading" style="margin: 0 0 24px; color: #202124; font-size: 36px; font-weight: 700; letter-spacing: -0.5px;">
              Welcome to <span style="color: #1a73e8;">Bazzix.</span>
            </h1>
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 24px;">
              <tr>
                <td align="left">
                  <a href="{dashboard_link}" class="button" style="display: inline-block; background-color: #1a73e8; color: #ffffff; font-size: 14px; font-weight: 600; text-decoration: none; padding: 12px 24px; border-radius: 4px;">
                    Get started
                  </a>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding: 0 40px;">
            <!-- Hero Image: You can replace this src with an actual hero banner from your assets -->
            <img src="https://images.unsplash.com/photo-1620712943543-bcc4688e7485?q=80&w=1200&auto=format&fit=crop" alt="Bazzix AI Platform" width="100%" style="display: block; max-width: 100%; height: auto; border-radius: 4px; border: 1px solid #e8eaed;">
          </td>
        </tr>
        <tr>
          <td class="content-cell" style="padding: 32px 40px 40px;">
            <p style="margin: 0 0 16px; color: #202124; font-size: 14px; font-weight: 600;">Hi there,</p>
            <p style="margin: 0 0 16px; color: #3c4043; font-size: 14px; line-height: 1.6;">
              We're thrilled to welcome you to Bazzix, your new intelligent AI platform. Bazzix is designed to help you streamline your workflows, generate powerful insights, and interact with cutting-edge AI models in real-time.
            </p>
            <p style="margin: 0 0 24px; color: #3c4043; font-size: 14px; line-height: 1.6;">
              To thank you for joining our growing community, we are offering you a special welcome gift of <strong>1,000 Bazzix credits</strong>. They have already been deposited into your account, and you can use them immediately to start exploring everything Bazzix has to offer.
            </p>
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 32px;">
              <tr>
                <td align="left">
                  <a href="{dashboard_link}" class="button" style="display: inline-block; background-color: #1a73e8; color: #ffffff; font-size: 14px; font-weight: 600; text-decoration: none; padding: 12px 24px; border-radius: 4px;">
                    Start exploring
                  </a>
                </td>
              </tr>
            </table>
            
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 32px; background-color: #f8f9fa; border-radius: 4px;">
              <tr>
                <td style="padding: 16px 20px;">
                  <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="width: 24px; vertical-align: middle; padding-right: 12px;">
                        <span style="color: #9aa0a6; font-size: 20px;">+</span>
                      </td>
                      <td style="color: #5f6368; font-size: 13px; line-height: 1.5; vertical-align: middle;">
                        Invite your team members to join your workspace to collaborate seamlessly on Bazzix. You can manage access from your dashboard.
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>

            <p style="margin: 0 0 8px; color: #3c4043; font-size: 14px;">Looking forward to seeing what you create,</p>
            <p style="margin: 0; color: #202124; font-size: 14px; font-weight: 600;">The Bazzix Team</p>
          </td>
        </tr>
        <tr>
          <td class="footer-cell" style="padding: 30px 40px; background-color: #f8f9fa; border-top: 1px solid #e8eaed;">
            <p style="margin: 0 0 16px; font-size: 18px; font-weight: 700; color: #5f6368; letter-spacing: -0.5px;">Bazzix</p>
            <p style="margin: 0 0 16px; color: #9aa0a6; font-size: 11px; line-height: 1.5;">
              Email preferences: We sent you this email because you recently signed up for a Bazzix account. If you don't want to receive such emails, click here to unsubscribe: <a href="{frontend_url}/unsubscribe" style="color: #1a73e8; text-decoration: underline;">{frontend_url}/unsubscribe</a>
            </p>
            <p style="margin: 0; color: #9aa0a6; font-size: 11px; line-height: 1.5;">
              &copy; {current_year} Bazzix LLC. All rights reserved.
            </p>
          </td>
        </tr>
      </table>
    </body>
    </html>
    '''
