#!/usr/bin/env node

// Test script to try different parameter combinations
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
  
  for (const [key, value] of Object.entries(fields)) {
    body += `--${boundary}\r\n`;
    body += `Content-Disposition: form-data; name="${key}"\r\n\r\n`;
    body += `${value}\r\n`;
  }
  
  body += `--${boundary}--\r\n`;
  
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

async function testParameterVariation(testName, formFields) {
  try {
    console.log(`\n🧪 Testing: ${testName}`);
    console.log(`Fields: ${Object.keys(formFields).join(', ')}`);
    
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
    
    console.log(`Status: ${response.statusCode}`);
    
    try {
      const jsonResponse = JSON.parse(response.body);
      if (response.statusCode === 200) {
        console.log('✅ SUCCESS!');
        console.log('Response:', JSON.stringify(jsonResponse, null, 2));
      } else {
        console.log('❌ Error:', jsonResponse.detail || jsonResponse.error || 'Unknown error');
      }
    } catch (e) {
      console.log('Response body:', response.body);
    }
    
  } catch (error) {
    console.log('❌ Request failed:', error.message);
  }
}

async function runTests() {
  console.log('🧪 Testing different parameter combinations');
  console.log('='.repeat(60));
  
  // Test 1: Current implementation
  await testParameterVariation('Current implementation (db_connection_string)', {
    question: TEST_CONFIG.question,
    db_connection_string: TEST_CONFIG.postgresUrl
  });
  
  // Test 2: Try db_uri
  await testParameterVariation('Using db_uri parameter', {
    question: TEST_CONFIG.question,
    db_uri: TEST_CONFIG.postgresUrl
  });
  
  // Test 3: Try database_url
  await testParameterVariation('Using database_url parameter', {
    question: TEST_CONFIG.question,
    database_url: TEST_CONFIG.postgresUrl
  });
  
  // Test 4: Try db_url (for postgres)
  await testParameterVariation('Using db_url parameter', {
    question: TEST_CONFIG.question,
    db_url: TEST_CONFIG.postgresUrl
  });
  
  // Test 5: Try connection_string
  await testParameterVariation('Using connection_string parameter', {
    question: TEST_CONFIG.question,
    connection_string: TEST_CONFIG.postgresUrl
  });
  
  // Test 6: Try postgres_url
  await testParameterVariation('Using postgres_url parameter', {
    question: TEST_CONFIG.question,
    postgres_url: TEST_CONFIG.postgresUrl
  });
  
  // Test 7: Try with db_dialect
  await testParameterVariation('Using db_uri + db_dialect', {
    question: TEST_CONFIG.question,
    db_uri: TEST_CONFIG.postgresUrl,
    db_dialect: 'postgresql'
  });
  
  console.log('\n' + '='.repeat(60));
  console.log('🏁 All tests completed');
}

runTests().catch(console.error);