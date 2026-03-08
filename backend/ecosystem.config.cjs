module.exports = {
  apps: [
    {
      name: 'ics-backend',
      cwd: '/root/kimi_dev/lunwen/ics-defense/backend',
      script: 'src/server.js',
      interpreter: 'node',
    },
    {
      name: 'ics-notification-worker',
      cwd: '/root/kimi_dev/lunwen/ics-defense/backend',
      script: 'src/workers/notification-worker.js',
      interpreter: 'node',
    },
  ],
};
