#!/usr/bin/env node

// Test script to verify backend API functionality
import https from 'https';
import http from 'http';
import { URL } from 'url';

// Test configuration
const TEST_CONFIG = {
  // Default backend URL - can be overridden via command line
  backendUrl: process.argv[2] || 'http://127.0.0.1:8000/chat/',
  
  // Test PostgreSQL URL (the one from your error message)
  postgresUrl: 'postgresql://neondb_owner:npg_CX6QwG9EZNkD@ep-rapid-leaf-a98umb0h-pooler.gwc.azure.neon.tech/neondb?sslmode=require',
  
  // Test question
  question: 'What tables are available in this database?'
};

console.log('🧪 Testing Backend API');
console.log('='.repeat(50));
console.log(`Backend URL: ${TEST_CONFIG.backendUrl}`);
console.log(`PostgreSQL URL: ${TEST_CONFIG.postgresUrl}`);
console.log(`Test Question: ${TEST_CONFIG.question}`);
console.log('='.repeat(50));

// Function to create multipart form data
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

// Function to make HTTP request
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

// Test function
async function testBackendAPI() {
  try {
    console.log('📡 Testing backend connection...');
    
    // Prepare form data
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
    
    console.log('📤 Sending POST request...');
    console.log('Form fields:', Object.keys(formFields));
    
    const response = await makeRequest(TEST_CONFIG.backendUrl, options, body);
    
    console.log('📥 Response received:');
    console.log(`Status Code: ${response.statusCode}`);
    console.log(`Headers:`, response.headers);
    console.log('Response Body:');
    console.log('-'.repeat(30));
    
    try {
      const jsonResponse = JSON.parse(response.body);
      console.log(JSON.stringify(jsonResponse, null, 2));
    } catch (e) {
      console.log(response.body);
    }
    
    console.log('-'.repeat(30));
    
    // Analyze response
    if (response.statusCode === 200) {
      console.log('✅ Backend is responding successfully!');
      
      try {
        const jsonResponse = JSON.parse(response.body);
        if (jsonResponse.answer) {
          console.log('✅ Backend provided an answer');
        }
        if (jsonResponse.sql) {
          console.log('✅ Backend generated SQL query');
        }
        if (jsonResponse.results) {
          console.log('✅ Backend returned query results');
        }
      } catch (e) {
        console.log('⚠️  Response is not valid JSON');
      }
    } else if (response.statusCode >= 400 && response.statusCode < 500) {
      console.log('❌ Client error - check request format or parameters');
    } else if (response.statusCode >= 500) {
      console.log('❌ Server error - backend may have issues');
    } else {
      console.log(`ℹ️  Unexpected status code: ${response.statusCode}`);
    }
    
  } catch (error) {
    console.log('❌ Failed to connect to backend:');
    console.log(`Error: ${error.message}`);
    
    if (error.code === 'ECONNREFUSED') {
      console.log('💡 Suggestion: Make sure the backend server is running');
    } else if (error.code === 'ENOTFOUND') {
      console.log('💡 Suggestion: Check the backend URL');
    }
  }
}

// Additional test for basic connectivity
async function testBasicConnectivity() {
  try {
    console.log('\n🔍 Testing basic connectivity...');
    
    const baseUrl = TEST_CONFIG.backendUrl.replace('/chat/', '');
    const response = await makeRequest(baseUrl, { method: 'GET' });
    
    console.log(`Basic connectivity test - Status: ${response.statusCode}`);
    
    if (response.statusCode === 200 || response.statusCode === 404) {
      console.log('✅ Backend server is reachable');
    } else {
      console.log('⚠️  Backend server responded with unexpected status');
    }
    
  } catch (error) {
    console.log('❌ Backend server is not reachable');
    console.log(`Error: ${error.message}`);
  }
}

// Run tests
async function runTests() {
  await testBasicConnectivity();
  await testBackendAPI();
  
  console.log('\n' + '='.repeat(50));
  console.log('🏁 Test completed');
  console.log('\nUsage: node test-backend.js [backend-url]');
  console.log('Example: node test-backend.js http://localhost:8000/chat/');
}

runTests().catch(console.error);