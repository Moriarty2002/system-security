package asymmetric.sign;

import asymmetric.CertificateGenerator;
import org.bouncycastle.asn1.pkcs.PKCSObjectIdentifiers;
import org.bouncycastle.asn1.pkcs.PrivateKeyInfo;
import org.bouncycastle.jce.provider.BouncyCastleProvider;

import java.io.*;
import java.security.*;
import java.security.cert.X509Certificate;

import org.bouncycastle.openssl.*;
import org.bouncycastle.openssl.jcajce.*;
import org.bouncycastle.operator.InputDecryptorProvider;
import org.bouncycastle.operator.OutputEncryptor;
import org.bouncycastle.pkcs.PKCS10CertificationRequest;
import org.bouncycastle.pkcs.PKCS8EncryptedPrivateKeyInfo;

@SuppressWarnings({"FieldCanBeLocal", "SameParameterValue"})
public class AsymmetricKeysUser {

    private final String CONFIG_DIR = "src/main/resources/asymmetric/";
    private final String PRIVATE_KEY_NAME = "private_key_user.pem";
    private final String PUBLIC_KEY_NAME = "public_key_user.pem";
    private final String KEY_PSW= "Unsecure psw";
    private final String USER_DN_NAME = "CN=localhost, OU=Dipartimento di Elettronica e Informatica, O=Università degli studi di Napoli Federico II, L=Napoli, ST=NA, C=IT";
    private final String SIGNATURE_ALG = "SHA256withRSA";

    AsymmetricKeysUser() {
        try {
            KeyPairGenerator kpg = KeyPairGenerator.getInstance("RSA");
            kpg.initialize(3072);
            KeyPair keyPair = kpg.generateKeyPair();

            saveEncryptedKeyPEM(keyPair, CONFIG_DIR, KEY_PSW);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }


    public PKCS10CertificationRequest generateCSR() {
        try {
            KeyPair keyPair = loadEncryptedKeyPEM(CONFIG_DIR, KEY_PSW);

            // include SANs in the CSR so the CA can copy them into the issued certificate
            // here we request DNS=localhost and IP=127.0.0.1 to match the CN used in USER_DN_NAME
            String[] sans = new String[]{"localhost", "127.0.0.1"};
            return CertificateGenerator.generateCSR(USER_DN_NAME, keyPair, SIGNATURE_ALG, sans);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    public void saveEncryptedKeyPEM(KeyPair keyPair, String filePath, String password) throws Exception {
        // store keys separately, because we still don't have a certificate signe by a CA

        // store encrypted private key as pem file
        try (Writer writer = new FileWriter(filePath + PRIVATE_KEY_NAME);
             JcaPEMWriter pemWriter = new JcaPEMWriter(writer)) {

            OutputEncryptor encryptor = new JceOpenSSLPKCS8EncryptorBuilder(
                    PKCSObjectIdentifiers.pbeWithSHAAnd3_KeyTripleDES_CBC
            )
                    .setProvider("BC")
                    .setRandom(new SecureRandom())
                    .setPassword(password.toCharArray())
                    .build();

            JcaPKCS8Generator pkcs8Generator = new JcaPKCS8Generator(keyPair.getPrivate(), encryptor);
            pemWriter.writeObject(pkcs8Generator);
        }

        // store public key as pem file
        try (Writer writer = new FileWriter(filePath + PUBLIC_KEY_NAME);
             JcaPEMWriter pemWriter = new JcaPEMWriter(writer)) {
            pemWriter.writeObject(keyPair.getPublic());
        }
    }

    private KeyPair loadEncryptedKeyPEM(String filePath, String password) throws Exception {
        Security.addProvider(new BouncyCastleProvider());

        PrivateKey privateKey;
        PublicKey publicKey;

        //  load and decrypt private key
        try (PEMParser parser = new PEMParser(new FileReader(filePath + PRIVATE_KEY_NAME))) {
            Object obj = parser.readObject();

            if (!(obj instanceof PKCS8EncryptedPrivateKeyInfo encryptedInfo)) {
                throw new IllegalStateException("Expected PKCS8EncryptedPrivateKeyInfo, got: " + obj.getClass());
            }

            // build decryptor
            InputDecryptorProvider decryptorProvider =
                    new JceOpenSSLPKCS8DecryptorProviderBuilder()
                            .setProvider("BC")
                            .build(password.toCharArray());

            PrivateKeyInfo privateKeyInfo = encryptedInfo.decryptPrivateKeyInfo(decryptorProvider);

            // convert to standard PrivateKey
            privateKey = new JcaPEMKeyConverter()
                    .setProvider("BC")
                    .getPrivateKey(privateKeyInfo);
        }

        // load public key
        try (PEMParser parser = new PEMParser(new FileReader(filePath + PUBLIC_KEY_NAME))) {
            Object obj = parser.readObject();

            publicKey = new JcaPEMKeyConverter()
                    .setProvider("BC")
                    .getPublicKey(
                            org.bouncycastle.asn1.x509.SubjectPublicKeyInfo.getInstance(obj)
                    );
        }

        return new KeyPair(publicKey, privateKey);
    }

    public void saveSignedCert(X509Certificate certificate) {
        // store public key as pem file
        try (Writer writer = new FileWriter(CONFIG_DIR + PUBLIC_KEY_NAME);
             JcaPEMWriter pemWriter = new JcaPEMWriter(writer)) {
            pemWriter.writeObject(certificate);
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }
 }