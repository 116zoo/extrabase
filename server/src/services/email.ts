import nodemailer from 'nodemailer'

export async function sendMagicLink(email: string, token: string): Promise<void> {
  const adminUrl = process.env.ADMIN_URL || 'http://localhost:3000'
  const magicUrl = `${adminUrl}/auth/magic?token=${token}`

  const transporter = nodemailer.createTransport({
    host: process.env.SMTP_HOST,
    port: Number(process.env.SMTP_PORT) || 587,
    auth: { user: process.env.SMTP_USER, pass: process.env.SMTP_PASS }
  })

  await transporter.sendMail({
    from: process.env.SMTP_FROM || 'noreply@seo-dashboard.com',
    to: email,
    subject: 'Lien de connexion SEO Dashboard',
    html: `<p>Cliquez pour vous connecter (valide 15 minutes) :</p>
           <p><a href="${magicUrl}">${magicUrl}</a></p>`
  })
}
