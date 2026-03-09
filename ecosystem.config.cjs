// PM2 Ecosystem Configuration — ICS Defense Platform
// Usage: pm2 start ecosystem.config.cjs

module.exports = {
  apps: [
    {
      name: 'ics-backend',
      cwd: '/root/kimi_dev/lunwen/ics-defense',
      script: 'uvicorn',
      args: 'agent.service:app --host 0.0.0.0 --port 8002',
      interpreter: 'python3',
      env: {
        DB_PATH: './data/ics_defense.db',
      },
    },
    {
      name: 'ics-frontend',
      cwd: '/root/kimi_dev/lunwen/ics-defense/frontend',
      script: 'npm',
      args: 'run dev',
      interpreter: 'none',
    },
  ],
};
