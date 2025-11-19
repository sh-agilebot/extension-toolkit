import { getLanguage } from '@agilebot/extension-runtime'
import { createI18n } from 'vue-i18n'

// 需要获取 App 当前的语言，进而切换用户插件的语言与 App 一致

// eslint-disable-next-line antfu/no-top-level-await
const currentLang = await getLanguage().catch(() => 'cn')

const i18n = createI18n({
  legacy: false,
  locale: currentLang,
  fallbackLocale: 'cn',
  messages: {
    cn: {
      runningStatus: {
        connectError: '连接机器人失败，请检查网络连接。',
        title: '运行信息',
        status: '运行状态：',
        velocity: '运行速度：',
        programName: '程序名称：',
        statusRunning: '正在运行',
        statusStopped: '静止',
      },
    },
    en: {
      runningStatus: {
        connectError: 'Failed to connect to robot, please check your network connection.',
        title: 'Running Information',
        status: 'Running Status:',
        velocity: 'Running Speed:',
        programName: 'Program Name:',
        statusRunning: 'Running',
        statusStopped: 'Stopped',
      },
    },
  },
})

export default i18n
