export type EmailSettings = {
  enabled: boolean
  smtp_host: string
  smtp_port: number
  smtp_username: string
  smtp_password_masked: string
  has_smtp_password: boolean
  smtp_use_ssl: boolean
  smtp_use_starttls: boolean
  email_from: string
  email_to: string
  subject_prefix: string
  site_base_url: string
  config_file: string
  daily_review_email_enabled: boolean
  daily_review_email_to: string
  daily_review_subject_prefix: string
  daily_snapshot_email_enabled: boolean
  daily_snapshot_email_to: string
  daily_snapshot_subject_prefix: string
  portfolio_action_alerts_email_enabled: boolean
  portfolio_action_alerts_email_to: string
  portfolio_action_alerts_subject_prefix: string
}

export type EmailSettingsPayload = {
  smtp_host: string
  smtp_port: number
  smtp_username: string
  smtp_password?: string
  smtp_use_ssl: boolean
  smtp_use_starttls: boolean
  email_from: string
  daily_review_email_enabled: boolean
  daily_review_email_to: string
  daily_review_subject_prefix?: string
  site_base_url?: string
  daily_snapshot_email_enabled: boolean
  daily_snapshot_email_to: string
  daily_snapshot_subject_prefix?: string
  portfolio_action_alerts_email_enabled?: boolean
  portfolio_action_alerts_email_to?: string
  portfolio_action_alerts_subject_prefix?: string
}

export type EmailSettingsMutationResponse = {
  settings: EmailSettings
  message: string
}

export type EmailTestPayload = {
  subject?: string
  message?: string
}

export type EmailTestResponse = {
  success: boolean
  message: string
  sent_to: string[]
  sent_at: string
}

export type EmailSendLatestResponse = {
  success: boolean
  sent: boolean
  report_date: string | null
  message: string
  task_id?: string | null
  status?: string | null
}
