#!/usr/bin/env node

// Debug script to check exactly what's being sent
import https from 'https';
import http from 'http';
import { URL } from 'url';

const TEST_CONFIG = {
  backendUrl: process.argv[2] || 'http://127.0.0.1:8000/chat/',
  postgresUrl: 'postgresql://neondb_owner:npg_CX6QwG9EZNkD@ep-rapid-leaf-a98umb0h-pooler.gwc.azure.neon.tech/neondb?sslmode=require',
  question: 'What tables are available in this database?'
};

function createMultipartFormData(fields) {
  const boundary = '----WebKitFormBoundary' + Math.random().toString(36).substring(2);
  let body = '';
  
  console.log('📝 Creating form data with fields:');
  for (const [key, value] of Object.entries(fields)) {
    console.log(`  ${key}: "${value}"`);
    body += `--${boundary}\r\n`;
    body += `Content-Disposition: form-data; name="${key}"\r\n\r\n`;
    body += `${value}\r\n`;
  }
  
  body += `--${boundary}--\r\n`;
  
  console.log('\n📦 Raw form data:');
  console.log(body);
  
  return {
    body,
    contentType: `multipart/form-data; boundary=${boundary}`
  };
}

function makeRequest(url, options, postData) {
  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(url);
    const isHttps = parsedUrl.protocol === 'https:';
    const client = isHttps ? https : http;
    
    const requestOptions = {
      hostname: parsedUrl.hostname,
      port: parsedUrl.port || (isHttps ? 443 : 80),
      path: parsedUrl.pathname + parsedUrl.search,
      method: options.method || 'GET',
      headers: options.headers || {}
    };
    
    console.log('\n🌐 Request details:');
    console.log('URL:', url);
    console.log('Method:', requestOptions.method);
    console.log('Headers:', options.headers);
    
    const req = client.request(requestOptions, (res) => {
      let data = '';
      
      res.on('data', (chunk) => {
        data += chunk;
      });
      
      res.on('end', () => {
        resolve({
          statusCode: res.statusCode,
          headers: res.headers,
          body: data
        });
      });
    });
    
    req.on('error', (error) => {
      reject(error);
    });
    
    if (postData) {
      req.write(postData);
    }
    
    req.end();
  });
}

// Test with different approaches
async function testDifferentFormats() {
  console.log('🧪 Testing different request formats');
  console.log('='.repeat(60));
  
  // Test 1: Standard multipart form
  console.log('\n🧪 Test 1: Standard multipart form');
  try {
    const formFields = {
      question: TEST_CONFIG.question,
      db_connection_string: TEST_CONFIG.postgresUrl
    };
    
    const { body, contentType } = createMultipartFormData(formFields);
    
    const options = {
      method: 'POST',
      headers: {
        'Content-Type': contentType,
        'Content-Length': Buffer.byteLength(body),
        'Accept': 'application/json'
      }
    };
    
    const response = await makeRequest(TEST_CONFIG.backendUrl, options, body);
    console.log(`\n📥 Response: ${response.statusCode}`);
    console.log(response.body);
    
  } catch (error) {
    console.log('❌ Error:', error.message);
  }
  
  // Test 2: JSON format
  console.log('\n🧪 Test 2: JSON format');
  try {
    const jsonData = {
      question: TEST_CONFIG.question,
      db_connection_string: TEST_CONFIG.postgresUrl
    };
    
    const jsonBody = JSON.stringify(jsonData);
    console.log('📝 JSON data:', jsonData);
    
    const options = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(jsonBody),
        'Accept': 'application/json'
      }
    };
    
    const response = await makeRequest(TEST_CONFIG.backendUrl, options, jsonBody);
    console.log(`\n📥 Response: ${response.statusCode}`);
    console.log(response.body);
    
  } catch (error) {
    console.log('❌ Error:', error.message);
  }
  
  // Test 3: URL encoded form
  console.log('\n🧪 Test 3: URL encoded form');
  try {
    const params = new URLSearchParams();
    params.append('question', TEST_CONFIG.question);
    params.append('db_connection_string', TEST_CONFIG.postgresUrl);
    
    const formBody = params.toString();
    console.log('📝 Form data:', formBody);
    
    const options = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': Buffer.byteLength(formBody),
        'Accept': 'application/json'
      }
    };
    
    const response = await makeRequest(TEST_CONFIG.backendUrl, options, formBody);
    console.log(`\n📥 Response: ${response.statusCode}`);
    console.log(response.body);
    
  } catch (error) {
    console.log('❌ Error:', error.message);
  }
  
  // Test 4: Simple question test
  console.log('\n🧪 Test 4: Simple question test (no DB)');
  try {
    const formFields = {
      question: 'Hello, are you working?'
    };
    
    const { body, contentType } = createMultipartFormData(formFields);
    
    const options = {
      method: 'POST',
      headers: {
        'Content-Type': contentType,
        'Content-Length': Buffer.byteLength(body),
        'Accept': 'application/json'
      }
    };
    
    const response = await makeRequest(TEST_CONFIG.backendUrl, options, body);
    console.log(`\n📥 Response: ${response.statusCode}`);
    console.log(response.body);
    
  } catch (error) {
    console.log('❌ Error:', error.message);
  }
}

testDifferentFormats().catch(console.error);