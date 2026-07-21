// Declarative pipeline for ml-model-cicd-gate.
//
// Gate philosophy: stages 1-6 fail fast and stop the build outright (bad
// lint, bad tests, bad metrics, bad image -- none of those should ever
// reach a deploy). Stage 9 onward is different on purpose: a failed smoke
// test does NOT abort the pipeline, it triggers an automatic rollback so
// the pipeline always ends in a known-good, notified state.
pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    environment {
        IMAGE_NAME              = 'ml-model-cicd-gate-api'
        // Assumes Jenkins has already checked out the repo to resolve this
        // Jenkinsfile, so .git is present before the environment block runs.
        GIT_COMMIT_SHORT        = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
        MODEL_ACCURACY_THRESHOLD = '0.95'
        APP_PORT                = '8000'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Lint') {
            steps {
                sh 'pip install -q -r requirements-dev.txt'
                sh 'ruff check .'
            }
        }

        stage('Unit Tests') {
            steps {
                sh 'pytest tests/ -q'
            }
        }

        stage('Train Model') {
            steps {
                sh 'python model/train.py'
            }
        }

        stage('Validate Metrics') {
            // The gate: a build with a model below threshold never gets an
            // image, never gets deployed. This is this project's single
            // quality gate -- see README.md for why it's one gate here and
            // not Zuul-style cross-repo speculative gating.
            steps {
                sh "python scripts/model_gate.py --threshold ${MODEL_ACCURACY_THRESHOLD}"
            }
        }

        stage('Build Docker Image') {
            steps {
                sh "docker build -t ${IMAGE_NAME}:${GIT_COMMIT_SHORT} --build-arg MODEL_VERSION=${GIT_COMMIT_SHORT} ."
            }
        }

        stage('Security Scan') {
            steps {
                // Falls back to a warning instead of failing the build when
                // trivy isn't installed on the agent, so this Jenkinsfile
                // stays runnable as documentation even without a full
                // security-scanning toolchain wired up.
                sh '''
                    if command -v trivy >/dev/null 2>&1; then
                        trivy image --exit-code 1 --severity CRITICAL,HIGH "${IMAGE_NAME}:${GIT_COMMIT_SHORT}"
                    else
                        echo "trivy not installed on this agent -- skipping scan (would fail the build on CRITICAL/HIGH CVEs)"
                    fi
                '''
            }
        }

        stage('Deploy') {
            // Blue-green: ansible/deploy.yml starts the new color, health-gates
            // it, and only then cuts traffic over -- the old color is never
            // touched until the new one has proven itself.
            steps {
                sh "ansible-playbook -i ansible/inventory.ini ansible/deploy.yml -e app_tag=${GIT_COMMIT_SHORT}"
            }
        }

        stage('Smoke Test') {
            steps {
                script {
                    try {
                        sh "python scripts/health_check.py --base-url http://localhost:${APP_PORT}"
                        env.SMOKE_TEST_FAILED = 'false'
                    } catch (Exception err) {
                        echo "smoke test failed: ${err.getMessage()}"
                        env.SMOKE_TEST_FAILED = 'true'
                    }
                }
            }
        }

        stage('Rollback') {
            when {
                environment name: 'SMOKE_TEST_FAILED', value: 'true'
            }
            steps {
                sh "./scripts/rollback.sh ${IMAGE_NAME} ml-model-api ${APP_PORT}"
            }
        }

        stage('Notify') {
            steps {
                script {
                    def failed = env.SMOKE_TEST_FAILED == 'true'
                    def status = failed ? 'failure' : 'success'
                    def message = failed
                        ? "smoke test failed for ${GIT_COMMIT_SHORT}, rolled back automatically"
                        : "${GIT_COMMIT_SHORT} deployed and passed smoke test"
                    sh "python scripts/notify.py --stage Notify --status ${status} --message '${message}'"
                }
            }
        }
    }

    post {
        failure {
            sh "python scripts/notify.py --stage Pipeline --status failure --message 'build ${env.BUILD_NUMBER} failed before deploy'"
        }
    }
}
