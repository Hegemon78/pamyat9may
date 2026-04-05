module.exports = {
  apps: [
    {
      name: 'pamyat9may-bot',
      cwd: '/var/www/pamyat9may/bot',
      script: 'bot.py',
      interpreter: 'python3',
      env: {
        BOT_TOKEN: '',       // Set in .env
        API_PORT: '8081',
        SITE_URL: 'https://pamyat9may.ru',
      },
      max_restarts: 10,
      restart_delay: 5000,
    }
  ]
};
