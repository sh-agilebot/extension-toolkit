<script setup lang="ts">
import { ref } from 'vue'
import { callEasyService } from '@agilebot/extension-runtime'

const a = ref(0);
const b = ref(0);
const c = ref(0);

const handleCalculate = async () => {
  const result = await callEasyService('MathService', 'add', {
    a: a.value,
    b: b.value
  })
  c.value = result
};
</script>


<template>
  <div class="math">
    <h1>加法计算器</h1>

    <div class="container">
      <label for="inputA">a:</label>
      <input type="number" v-model="a" placeholder="输入第一个数字">

      <label for="inputB">b:</label>
      <input type="number" v-model="b" placeholder="输入第二个数字">

      <button @click="handleCalculate">计算 a + b</button>
    </div>

    <div class="result">
      <p>结果: <span>{{ c }}</span></p>
    </div>
  </div>
</template>

<style scoped>
  .math {
    padding: 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .container {
    margin-top: 20px;
  }

  input {
    padding: 5px;
    margin: 10px;
    font-size: 1em;
  }

  button {
    padding: 5px 10px;
    font-size: 1em;
    cursor: pointer;
  }

  .result {
    margin-top: 20px;
    font-size: 1.2em;
  }
</style>