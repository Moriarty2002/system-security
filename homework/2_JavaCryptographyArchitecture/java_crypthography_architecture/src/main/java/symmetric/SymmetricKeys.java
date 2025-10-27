package symmetric;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.SecureRandom;
import java.util.Base64;
import java.util.Properties;

public class SymmetricKeys {

    private static final String CONFIG_DIR = "src/main/resources/symmetric";
    private static final String CONFIG_FILE = "crypto.properties";
    private static final Path CONFIG_PATH = Paths.get(CONFIG_DIR, CONFIG_FILE);

    private static final String KEY_PROPERTY = "AES_KEY";
    private static final String IV_PROPERTY = "AES_IV";
    private static final String ALGORITHM = "AES";
    private static final String CIPHER_TRANSFORMATION = "AES/CBC/PKCS5Padding";

    static void main(String[] args) throws Exception {

        // generate key and init vector
        KeyGenerator keyGen = KeyGenerator.getInstance(ALGORITHM);
        keyGen.init(256);
        SecretKey secretKey = keyGen.generateKey();

        byte[] iv = new byte[16];
        new SecureRandom().nextBytes(iv);
        IvParameterSpec ivSpec = new IvParameterSpec(iv);

        storeKeyAndIv(secretKey, ivSpec);
        System.out.println("Generated key: " + Base64.getEncoder().encodeToString(secretKey.getEncoded()));
        System.out.println("Generated IV:  " + Base64.getEncoder().encodeToString(ivSpec.getIV()));
        System.out.println("-------------------------------------------------");

        // encrypt
        String plainText = "! this is a msg !";
        Cipher cipherEncrypt = Cipher.getInstance(CIPHER_TRANSFORMATION);
        cipherEncrypt.init(Cipher.ENCRYPT_MODE, secretKey, ivSpec);
        byte[] cipherText = cipherEncrypt.doFinal(plainText.getBytes());

        System.out.println("Original text: " + plainText);
        System.out.println("Encrypted text: " + Base64.getEncoder().encodeToString(cipherText));
        System.out.println("-------------------------------------------------");


        // decipher
        SecretKey loadedKey = loadKey();
        IvParameterSpec loadedIvSpec = loadIv();

        System.out.println("Loaded key: " + Base64.getEncoder().encodeToString(loadedKey.getEncoded()));
        System.out.println("Loaded IV:  " + Base64.getEncoder().encodeToString(loadedIvSpec.getIV()));

        Cipher cipherDecrypt = Cipher.getInstance(CIPHER_TRANSFORMATION);
        cipherDecrypt.init(Cipher.DECRYPT_MODE, loadedKey, loadedIvSpec);
        String decryptedText = new String(cipherDecrypt.doFinal(cipherText));

        System.out.println("Deciphered text: " + decryptedText);
    }

    /**
     * Stores the SecretKey and IV in a properties file.
     *
     * @param key    The SecretKey to store.
     * @param ivSpec The IvParameterSpec to store.
     * @throws Exception if writing fails.
     */
    public static void storeKeyAndIv(SecretKey key, IvParameterSpec ivSpec) throws Exception {
        Properties props = new Properties();
        // Encode bytes as Base64 strings
        props.setProperty(KEY_PROPERTY, Base64.getEncoder().encodeToString(key.getEncoded()));
        props.setProperty(IV_PROPERTY, Base64.getEncoder().encodeToString(ivSpec.getIV()));

        Files.createDirectories(CONFIG_PATH.getParent());

        try (OutputStream out = Files.newOutputStream(CONFIG_PATH)) {
            props.store(out, "AES Cryptographic Configuration");
        }
    }

    /**
     * Loads the SecretKey from the properties file.
     *
     * @return The loaded SecretKey.
     * @throws Exception if reading or decoding fails.
     */
    public static SecretKey loadKey() throws Exception {
        Properties props = loadProperties();
        String keyBase64 = props.getProperty(KEY_PROPERTY);
        if (keyBase64 == null) {
            throw new Exception("Property " + KEY_PROPERTY + " not found in " + CONFIG_PATH);
        }

        byte[] keyBytes = Base64.getDecoder().decode(keyBase64);
        return new SecretKeySpec(keyBytes, ALGORITHM);
    }

    /**
     * Loads the IvParameterSpec from the properties file.
     *
     * @return The loaded IvParameterSpec.
     * @throws Exception if reading or decoding fails.
     */
    public static IvParameterSpec loadIv() throws Exception {
        Properties props = loadProperties();
        String ivBase64 = props.getProperty(IV_PROPERTY);
        if (ivBase64 == null) {
            throw new Exception("Property " + IV_PROPERTY + " not found in " + CONFIG_PATH);
        }

        byte[] ivBytes = Base64.getDecoder().decode(ivBase64);
        return new IvParameterSpec(ivBytes);
    }

    private static Properties loadProperties() throws Exception {
        Properties props = new Properties();
        if (!Files.exists(CONFIG_PATH)) {
            throw new Exception("Configuration file not found: " + CONFIG_PATH);
        }

        try (InputStream in = Files.newInputStream(CONFIG_PATH)) {
            props.load(in);
        }
        return props;
    }
}