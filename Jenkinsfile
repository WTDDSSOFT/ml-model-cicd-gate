// Declarative pipeline for ml-model-cicd-gate.
//
// Gate philosophy: stages 1-6 fail fast and stop the build outright (bad
// lint, bad tests, bad metrics, bad image -- none of those should ever
// reach a deploy). Stage 9 onward is different on purpose: a failed smoke
// test does NOT abort the pipeline, it triggers an automatic rollback so
// the pipeline always ends in a known-good state -- but the build is
// still marked UNSTABLE in that case, never a silent green.
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
        // Unset by default: this portfolio project has no real registry.
        // Set it on the Jenkins job (or -e REGISTRY_URL=...) to exercise
        // the Push Image stage and the registry-pull path in Ansible.
        REGISTRY_URL             = "${env.REGISTRY_URL ?: ''}"
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
                sh 'pytest tests/ -q --junitxml=test-results/junit.xml'
            }
            post {
                // Publish whatever the suite produced even if it failed --
                // a stage failure here still needs to show up in the test
                // report, not just as a red pipeline stage.
                always {
                    junit testResults: 'test-results/junit.xml', allowEmptyResults: true
                }
            }
        }

        stage('Train Model') {
            steps {
                sh 'python model/train.py'
            }
        }

        stage('Evaluate Model') {
            // Reloads the saved model.pt from disk and recomputes metrics.json
            // against it -- this is what the gate actually scores, not the
            // number train.py happened to compute in-memory before saving.
            // They should agree (there's no dropout/batchnorm in DigitCNN to
            // make them diverge), but the gate should validate the shipped
            // artifact, not trust the training process's self-report.
            steps {
                sh 'python model/evaluate.py'
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
            // Mandatory, not advisory: if trivy isn't already on the agent,
            // install it locally into the workspace instead of skipping the
            // scan. Either way a CRITICAL/HIGH finding fails the build.
            steps {
                sh '''
                    if ! command -v trivy >/dev/null 2>&1; then
                        echo "trivy not found on this agent -- installing into ./.trivy-bin"
                        curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh \
                            | sh -s -- -b ./.trivy-bin
                        export PATH="$PWD/.trivy-bin:$PATH"
                    fi
                    trivy image --exit-code 1 --severity CRITICAL,HIGH "${IMAGE_NAME}:${GIT_COMMIT_SHORT}"
                '''
            }
        }

        stage('Push Image') {
            // In a real deployment this is what makes the image reachable
            // by the target hosts: ansible/deploy.yml's "pull" task fetches
            // it from here rather than assuming it's already sitting on the
            // same Docker daemon Jenkins just built it on. No registry is
            // wired up for this portfolio project, so the stage is a no-op
            // unless REGISTRY_URL is set on the job.
            when {
                expression { return REGISTRY_URL?.trim() }
            }
            steps {
                sh """
                    docker tag ${IMAGE_NAME}:${GIT_COMMIT_SHORT} ${REGISTRY_URL}/${IMAGE_NAME}:${GIT_COMMIT_SHORT}
                    docker push ${REGISTRY_URL}/${IMAGE_NAME}:${GIT_COMMIT_SHORT}
                """
            }
        }

        stage('Deploy') {
            // Blue-green: ansible/deploy.yml starts the new color, health-gates
            // it, and only then cuts traffic over -- the old color is never
            // touched until the new one has proven itself. app_registry is
            // only passed when Push Image actually ran; otherwise the
            // playbook deploys the image it finds on the local daemon.
            steps {
                script {
                    def registryArg = REGISTRY_URL?.trim() ? "-e app_registry=${REGISTRY_URL}" : ''
                    sh "ansible-playbook -i ansible/inventory.ini ansible/deploy.yml -e app_tag=${GIT_COMMIT_SHORT} ${registryArg}"
                }
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
                script {
                    // rollback.sh already exited non-zero (failing this stage)
                    // if it couldn't recover. Getting here means recovery
                    // worked -- but a build that needed to roll back is not a
                    // clean success and must never show green.
                    currentBuild.result = 'UNSTABLE'
                }
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

                    if (!failed) {
                        // Snapshot this build's metrics as the new production
                        // baseline so the next build's Validate Metrics stage
                        // can catch a regression, not just an absolute-threshold
                        // failure. Lives in the Jenkins workspace, not git --
                        // see scripts/model_gate.py for what happens when it's
                        // missing (first build on a node, or a wiped workspace).
                        sh 'cp model/artifacts/metrics.json model/artifacts/production_metrics.json'
                    }
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'model/artifacts/model.pt,model/artifacts/metrics.json',
                              allowEmptyArchive: true,
                              fingerprint: true
        }
        failure {
            sh "python scripts/notify.py --stage Pipeline --status failure --message 'build ${env.BUILD_NUMBER} failed before deploy'"
        }
    }
}
